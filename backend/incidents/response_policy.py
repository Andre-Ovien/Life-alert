"""Opt-in simulation policy. Candidate suitability is explicitly reviewed by a
coordinator, not inferred from diagnosis or an unverified distance estimate.
"""
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied,ValidationError
from common.audit import audit
from operations.models import ResponsePolicy,Coordinator,Team
from .models import Incident,ResponsePlan,ResponsePlanReview,ApprovedCrewCandidate,Notification,OPEN_STATES
from .access import require_coordinator
from .workflow import escalate,enqueue_notifications


@transaction.atomic
def configure_plan(actor,incident_id,enabled,team_ids,review_reference):
    incident=Incident.objects.select_for_update().select_related('child').get(pk=incident_id)
    require_coordinator(actor,incident)
    if incident.state not in OPEN_STATES or incident.coordinator_owner_id!=actor.pk:
        raise PermissionDenied('Current incident owner must approve the response plan.')
    if not review_reference.strip() or len(team_ids)!=len(set(team_ids)):
        raise ValidationError('Review reference and unique ordered teams required.')
    teams=list(Team.objects.filter(pk__in=team_ids,region_id=incident.region_id))
    if len(teams)!=len(team_ids):raise ValidationError('Every candidate must belong to this incident region.')
    previous=ResponsePlan.objects.filter(incident=incident).first()
    revision=previous.revision+1 if previous else 1
    plan,_=ResponsePlan.objects.update_or_create(incident=incident,defaults={'revision':revision,**{'enabled':enabled,'reviewed_by':actor,
        'reviewed_location_revision':incident.location_revision,'reviewed_care_version':incident.child.current_version,'review_reference':review_reference}})
    ResponsePlanReview.objects.create(plan=plan,revision=revision,reviewer=actor,review_reference=review_reference,
        candidate_ids=[str(pk) for pk in team_ids],care_version=plan.reviewed_care_version)
    plan.candidates.all().delete()  # Derived candidate configuration; history remains audited.
    ApprovedCrewCandidate.objects.bulk_create([ApprovedCrewCandidate(plan=plan,team_id=pk,priority=i) for i,pk in enumerate(team_ids)])
    audit(actor,'response.plan_reviewed',incident,plan_id=str(plan.id),enabled=enabled,teams=[str(pk) for pk in team_ids],care_version=plan.reviewed_care_version)
    return plan


def _alert(incident,audience,context_key,user=None,team=None):
    Notification.objects.get_or_create(incident=incident,audience=audience,context_key=context_key,
        defaults={'recipient_user':user,'recipient_team':team})
    enqueue_notifications(incident)


@transaction.atomic
def tick_response_policy(incident_id,at=None):
    from .services import offer_team
    incident=Incident.objects.select_for_update(of=('self',)).select_related('child','coordinator_owner').get(pk=incident_id)
    if incident.state not in OPEN_STATES or not incident.region_id:return
    policy=ResponsePolicy.objects.select_related('primary__user','backup__user').filter(region_id=incident.region_id,enabled=True).first()
    if not policy:return
    # Fail closed if incomplete configuration was inserted outside the API.
    if not (policy.primary_id and policy.backup_id and policy.offer_seconds and policy.ownership_seconds and policy.review_reference):return
    at=at or timezone.now()
    primary_ok=policy.primary.region_id==incident.region_id and policy.primary.on_duty and policy.primary.user.is_active
    backup_ok=policy.backup.region_id==incident.region_id and policy.backup.on_duty and policy.backup.user.is_active
    if primary_ok:_alert(incident,'coordinator','policy-primary',user=policy.primary.user)
    owner_ok=bool(incident.coordinator_owner_id and incident.coordinator_owner.is_active and
        Coordinator.objects.filter(region_id=incident.region_id,user_id=incident.coordinator_owner_id).exists())
    if not owner_ok and at>=incident.accepted_at+timedelta(seconds=policy.ownership_seconds):
        task=escalate(incident,'coordinator_unclaimed','ownership:'+str(incident.id))
        if backup_ok:_alert(incident,'backup','backup:'+str(task.id),user=policy.backup.user)
    plan=ResponsePlan.objects.filter(incident=incident,enabled=True).first()
    if not plan or not plan.reviewed_by.is_active or not Coordinator.objects.filter(user_id=plan.reviewed_by_id,region_id=incident.region_id).exists() or not owner_ok or incident.state not in ['triage','active']:return
    if plan.reviewed_location_revision!=incident.location_revision:
        escalate(incident,'location_changed','location-revision:'+str(incident.id)+':'+str(incident.location_revision))
        return
    if plan.reviewed_care_version!=incident.child.current_version:
        escalate(incident,'care_changed','care-version:'+str(incident.id)+':'+str(incident.child.current_version))
        return
    if incident.assignments.filter(state__in=['offered','accepted','en_route','arrived']).exists():return
    # Same order as manual offering: incident -> active owner -> team.
    from .access import require_active_adult
    require_active_adult(incident.coordinator_owner)
    attempted=set(incident.assignments.values_list('team_id',flat=True))
    for candidate in plan.candidates.select_related('team').order_by('priority'):
        team=Team.objects.select_for_update().get(pk=candidate.team_id)
        if team.pk in attempted or team.region_id!=incident.region_id or not team.available or not team.on_duty or not team.members.filter(is_active=True).exists():continue
        assignment=offer_team(incident.coordinator_owner,incident.id,team.id,True)
        assignment.deadline=at+timedelta(seconds=policy.offer_seconds)
        assignment.save(update_fields=['deadline'])
        audit(None,'response.approved_candidate_offered',incident,assignment_id=str(assignment.id),plan_id=str(plan.id))
        return
    task=escalate(incident,'crew_exhausted','crew-exhausted:'+str(incident.id)+':'+str(plan.revision))
    if backup_ok:_alert(incident,'backup','crew-backup:'+str(task.id),user=policy.backup.user)
