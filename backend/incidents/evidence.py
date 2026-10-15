import hashlib,json
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied,ValidationError
from common.audit import audit
from families.access import is_device,require_child_access
from families.models import Device
from operations.models import Coordinator
from .access import require_coordinator,coordinator
from .models import Incident,LocationUpdate,IncidentHandover,Notification,ResponsePlan,OPEN_STATES
from .workflow import escalate,enqueue_notifications


@transaction.atomic
def report_location(actor,incident_id,request_id,location):
    from .services import location_context
    incident=Incident.objects.select_for_update().get(pk=incident_id)
    if incident.state not in OPEN_STATES:raise ValidationError('Incident is closed.')
    if is_device(actor):
        device=Device.objects.get(pk=actor.device.id)
        if device.child_id!=incident.child_id or device.revoked_at or (device.expires_at and device.expires_at<=timezone.now()):raise PermissionDenied()
    elif not coordinator(actor,incident):require_child_access(actor,incident.child,'request_help')
    serialized=json.loads(json.dumps(location,default=lambda item:item.isoformat()))
    fingerprint=hashlib.sha256(json.dumps(serialized,sort_keys=True).encode()).hexdigest()
    previous=LocationUpdate.objects.filter(incident=incident,request_id=request_id).first()
    if previous:
        if previous.fingerprint!=fingerprint:raise ValidationError('Location request ID reused with different data.')
        return previous
    try:quality,region=location_context(location,timezone.now())
    except ValidationError:quality,region='outside_coverage',None
    obj=LocationUpdate.objects.create(incident=incident,request_id=request_id,fingerprint=fingerprint,location=serialized,
        quality=quality,matched_region=region,actor=None if is_device(actor) else actor,
        device_id=actor.device.id if is_device(actor) else None)
    incident.review_required=True;incident.save(update_fields=['review_required'])
    audit(actor,'incident.location_reported',incident,update_id=str(obj.id),quality=quality)
    return obj


@transaction.atomic
def review_location(actor,incident_id,update_id,accept,reference):
    incident=Incident.objects.select_for_update().get(pk=incident_id);require_coordinator(actor,incident)
    obj=LocationUpdate.objects.select_for_update().get(pk=update_id,incident=incident)
    if incident.state not in OPEN_STATES or obj.status!='pending' or not reference.strip():raise ValidationError('Pending update, open incident and review reference required.')
    obj.status='verified' if accept else 'rejected';obj.reviewed_by=actor;obj.review_reference=reference;obj.save()
    if accept:
        incident.location=obj.location;incident.location_quality=obj.quality
        incident.location_revision+=1;incident.review_required=True
        incident.save(update_fields=['location','location_quality','location_revision','review_required'])
        if obj.matched_region_id!=incident.region_id:
            escalate(incident,'region_review','region-update:'+str(obj.id))
        for assignment in incident.assignments.filter(state__in=['accepted','en_route','arrived']):
            Notification.objects.get_or_create(incident=incident,audience='crew',context_key='location:'+str(obj.id)+':'+str(assignment.team_id),
                defaults={'recipient_team_id':assignment.team_id})
        Notification.objects.get_or_create(incident=incident,audience='coordinator',context_key='location:'+str(obj.id),defaults={'recipient_user':actor})
        enqueue_notifications(incident)
    audit(actor,'incident.location_reviewed',incident,update_id=str(obj.id),accepted=accept,quality=obj.quality)
    return obj


@transaction.atomic
def request_handover(actor,incident_id,target_id,reference):
    incident=Incident.objects.select_for_update().get(pk=incident_id);require_coordinator(actor,incident)
    if incident.state not in OPEN_STATES or incident.coordinator_owner_id!=actor.pk or not reference.strip():raise PermissionDenied('Current open incident owner and review reference required.')
    target=Coordinator.objects.select_related('region','user').get(pk=target_id)
    if target.region_id==incident.region_id or not target.region.enabled or not target.user.is_active or not target.on_duty:
        raise ValidationError('An active on-duty coordinator in a different enabled region is required.')
    if IncidentHandover.objects.filter(incident=incident,status='pending').exists():raise ValidationError('A regional handover is already pending.')
    obj=IncidentHandover.objects.create(incident=incident,source_region=incident.region,target=target,source_owner=actor,reference=reference)
    # Alert is a pending handover task, never an accepted ownership claim.
    Notification.objects.get_or_create(incident=incident,audience='coordinator',context_key='handover:'+str(obj.id),defaults={'recipient_user':target.user})
    enqueue_notifications(incident)
    audit(actor,'incident.region_handover_requested',incident,handover_id=str(obj.id),target_region=str(target.region_id))
    return obj


@transaction.atomic
def accept_handover(actor,pk):
    item=IncidentHandover.objects.select_related('target').get(pk=pk)
    incident=Incident.objects.select_for_update().get(pk=item.incident_id)
    item=IncidentHandover.objects.select_for_update().select_related('target__region','target__user').get(pk=pk)
    from .access import require_active_adult
    require_active_adult(actor)
    if is_device(actor) or item.target.user_id!=actor.pk:raise PermissionDenied('Named receiving coordinator required.')
    if item.status!='pending' or incident.state not in OPEN_STATES or incident.region_id!=item.source_region_id or incident.coordinator_owner_id!=item.source_owner_id:
        raise ValidationError('Handover is stale, closed or already consumed.')
    if not item.target.user.is_active or not item.target.region.enabled or not item.target.on_duty:raise ValidationError('Receiving coordinator or region is unavailable.')
    incident.region=item.target.region;incident.coordinator_owner=actor
    if incident.state=='received':incident.state='triage'
    incident.review_required=True;incident.save(update_fields=['region','coordinator_owner','state','review_required'])
    ResponsePlan.objects.filter(incident=incident).update(enabled=False)
    item.status='accepted';item.accepted_at=timezone.now();item.save(update_fields=['status','accepted_at'])
    audit(actor,'incident.region_handover_accepted',incident,handover_id=str(item.id),region_id=str(incident.region_id))
    return item


@transaction.atomic
def end_handover(actor,pk,target,reference):
    item=IncidentHandover.objects.get(pk=pk)
    incident=Incident.objects.select_for_update().get(pk=item.incident_id)
    item=IncidentHandover.objects.select_for_update().select_related('target').get(pk=pk)
    if is_device(actor):raise PermissionDenied()
    if target=='declined':
        if item.target.user_id!=actor.pk:raise PermissionDenied('Named receiving coordinator required.')
    elif target=='cancelled':
        if incident.coordinator_owner_id!=actor.pk:raise PermissionDenied('Current incident owner required.')
    else:raise ValidationError('Unsupported handover decision.')
    if item.status!='pending' or not reference.strip():raise ValidationError('Pending handover and decision reference required.')
    item.status=target;item.save(update_fields=['status'])
    from .models import ProgressNote
    ProgressNote.objects.create(incident=incident,author=actor,action_taken='Regional handover '+target+': '+reference,next_steps='Current owner retains responsibility; review alternative receiving coordinator.')
    if target=='declined':escalate(incident,'region_review','handover-declined:'+str(item.id))
    audit(actor,'incident.region_handover_'+target,incident,handover_id=str(item.id))
    return item
