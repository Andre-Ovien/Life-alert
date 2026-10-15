import uuid
import hashlib
import json
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError, NotFound
from common.audit import audit
from families.access import require_guardian, is_device, require_child_access
from families.models import Child, Device, Household, Entitlement
from operations.models import Region, Team, Facility
from .access import require_coordinator
from .adapters import LocalBilling, SimulatedEMS, SimulatedNotifications
from .models import Incident, HelpRequest, Assignment, EMSOperation, Notification, Placement, OPEN_STATES


def lock_incident(pk):
    try:
        return Incident.objects.select_for_update(of=('self',)).select_related('child', 'region').get(pk=pk)
    except Incident.DoesNotExist:
        raise NotFound()


def location_context(location, at):
    if not location or location.get('latitude') is None:
        return 'missing', None
    captured = location['captured_at']
    age = (at - captured).total_seconds()
    quality = 'fresh'
    if age < -30 or age > settings.LOCATION_MAX_AGE_SECONDS:
        quality = 'stale'
    elif location['accuracy_meters'] > settings.LOCATION_MAX_ACCURACY_METERS:
        quality = 'inaccurate'
    region = None
    if quality == 'fresh':
        regions = Region.objects.filter(
            enabled=True, min_lat__lte=location['latitude'], max_lat__gte=location['latitude'],
            min_lon__lte=location['longitude'], max_lon__gte=location['longitude'])
        # Ambiguous coverage requires review, not arbitrary selection.
        if regions.count() == 1:
            region = regions.first()
        elif not regions.exists():
            raise ValidationError({'coverage': 'outside_service_area', 'emergency_call_separate': True})
        else:
            quality = 'ambiguous_region'
    return quality, region


@transaction.atomic
def create_incident(actor, child_id, key, location):
    try:
        child = Child.objects.select_related('household').get(pk=child_id)
    except Child.DoesNotExist:
        raise NotFound()
    # All entitlement changes and acceptance use this household lock first.
    Household.objects.select_for_update().get(pk=child.household_id)
    if is_device(actor):
        device = Device.objects.select_for_update().get(pk=actor.device.pk)
        if device.revoked_at or (device.expires_at and device.expires_at<=timezone.now()) or device.child_id != child.id:
            raise PermissionDenied('Device not authorized.')
    else:
        require_child_access(actor,child,'request_help')
    serialized = json.loads(json.dumps(location, default=lambda value: value.isoformat()))
    fingerprint = hashlib.sha256(json.dumps(serialized, sort_keys=True).encode()).hexdigest()
    previous = HelpRequest.objects.filter(child=child, key=key).select_related('incident').first()
    if previous:
        if previous.fingerprint != fingerprint:
            raise ValidationError({'request_id': 'Reused with different location data.'})
        audit(actor, 'incident.replayed', previous.incident)
        return previous.incident, 'replayed'
    at = timezone.now()
    entitlement = Entitlement.objects.select_for_update().filter(household=child.household).first()
    if not LocalBilling().eligible(entitlement, at):
        raise ValidationError({'entitlement': 'active_subscription_required', 'emergency_call_separate': True})
    current = Incident.objects.filter(child=child, state__in=OPEN_STATES).first()
    if current:
        HelpRequest.objects.create(child=child, key=key, fingerprint=fingerprint, location=serialized, incident=current)
        current.review_required = True
        current.save(update_fields=['review_required'])
        audit(actor, 'incident.followup_requires_review', current, request_id=str(key))
        return current, 'followup_requires_review'
    quality, region = location_context(location, at)
    from families.services import ensure_version
    care_version = ensure_version(child.id,actor)
    incident = Incident.objects.create(
        care_version=care_version,
        child=child, region=region, accepted_at=at, accepted_entitlement_until=entitlement.ends_at,
        location=serialized, location_quality=quality,
        saved_address_fallback=child.saved_address if quality != 'fresh' else '',
        review_required=quality != 'fresh',
    )
    HelpRequest.objects.create(child=child, key=key, fingerprint=fingerprint, location=serialized, incident=incident)
    # Independent durable jobs, not a parent approval dependency.
    Notification.objects.bulk_create([
        Notification(incident=incident, audience='guardian'), Notification(incident=incident, audience='coordinator')])
    EMSOperation.objects.create(incident=incident)
    from .workflow import enqueue_notifications
    enqueue_notifications(incident)
    audit(actor, 'incident.accepted', incident, location_quality=quality)
    return incident, 'accepted'


@transaction.atomic
def revoke_device(actor, pk):
    device = Device.objects.select_related('child').get(pk=pk)
    Household.objects.select_for_update().get(pk=device.child.household_id)
    require_child_access(actor,device.child,'manage_devices')
    device = Device.objects.select_for_update().get(pk=pk)
    device.revoked_at = timezone.now()
    device.save(update_fields=['revoked_at'])
    audit(actor, 'device.revoked', device)
    return device


def branches_reconciled(incident):
    return not incident.assignments.exclude(state__in=['complete', 'declined', 'timed_out']).exists() and not incident.placements.exclude(state__in=['released', 'cancelled']).exists() and incident.ems.state in ['closed', 'no_dispatch']


@transaction.atomic
def transition(actor, pk, target, outcome='', reconciled=False, outcome_details=None):
    incident = lock_incident(pk)
    require_coordinator(actor, incident)
    allowed = {'received': {'triage', 'cancelled'}, 'triage': {'active', 'cancelled'}, 'active': {'resolved', 'cancelled'}}
    if target not in allowed.get(incident.state, set()):
        raise ValidationError({'state': 'Invalid lifecycle transition.'})
    if target == 'triage':
        incident.coordinator_owner = actor
    if target in ['resolved', 'cancelled']:
        if incident.escalations.exclude(status='resolved').exists():
            raise ValidationError('Resolve outstanding response escalations before closing.')
        if incident.coordinator_owner_id not in [None, actor.pk]:
            raise PermissionDenied('Claim coordinator ownership before disposition.')
        incident.coordinator_owner = actor
        if not outcome.strip():
            raise ValidationError({'outcome': 'A disposition is required.'})
        if incident.response_started_at and (not reconciled or not branches_reconciled(incident)):
            raise ValidationError({'reconciled': 'Active crew, EMS and placement work must be completed/reconciled first.'})
        if target == 'cancelled' and incident.response_started_at and not incident.cancellation_requested:
            raise ValidationError({'cancellation': 'Coordinator review request is required after response starts.'})
        # Even early cancellations explicitly close the as-yet unstarted EMS task.
        if not incident.response_started_at:
            incident.ems.state = 'closed'
            incident.ems.evidence = 'Closed before response started by coordinator disposition'
            incident.ems.save()
        if target=='resolved':
            required={'assistance','handover','ems_disposition','followup'}
            if not isinstance(outcome_details,dict) or set(outcome_details)!=required or any(not isinstance(value,str) or not value.strip() or len(value)>2000 for value in outcome_details.values()):
                raise ValidationError({'outcome_details':'Record assistance, verified handover/disposition, actual EMS disposition and follow-up ownership.'})
            incident.outcome_details=outcome_details
        from .models import IncidentHandover
        IncidentHandover.objects.filter(incident=incident,status='pending').update(status='cancelled')
        incident.closed_at=timezone.now();incident.closed_by=actor
        incident.outcome = outcome
    if target == 'active':
        incident.response_started_at = incident.response_started_at or timezone.now()
    old = incident.state
    incident.state = target
    incident.save()
    audit(actor, 'incident.transition', incident, previous=old, target=target, reconciled=reconciled)
    return incident


@transaction.atomic
def request_cancellation(actor, pk):
    incident = lock_incident(pk)
    if is_device(actor):
        if actor.device.child_id != incident.child_id:
            raise PermissionDenied()
    else:
        from families.access import guardian
        from .access import coordinator
        from families.access import child_access
        if not (child_access(actor,incident.child,'request_help') or coordinator(actor, incident)):
            raise PermissionDenied()
    if incident.state not in OPEN_STATES:
        raise ValidationError('Incident is closed.')
    incident.cancellation_requested = True
    incident.save(update_fields=['cancellation_requested'])
    audit(actor, 'incident.cancellation_requested', incident)
    return incident


@transaction.atomic
def offer_team(actor, pk, team_id, suitability_confirmed):
    incident = lock_incident(pk)
    require_coordinator(actor, incident)
    if incident.state not in ['triage', 'active']:
        raise ValidationError('Triage is required before crew offers.')
    team = Team.objects.select_for_update().filter(pk=team_id, region_id=incident.region_id, available=True, on_duty=True).first()
    if not team or not suitability_confirmed:
        raise ValidationError('Available regional team and coordinator suitability confirmation required.')
    if incident.assignments.filter(state__in=['offered', 'accepted', 'en_route', 'arrived']).exists():
        raise ValidationError('A live offer/assignment already exists.')
    assignment = Assignment.objects.create(incident=incident, team=team, deadline=timezone.now()+timedelta(seconds=settings.CREW_OFFER_SECONDS))
    incident.response_started_at = incident.response_started_at or timezone.now()
    incident.save(update_fields=['response_started_at'])
    from .workflow import enqueue_notifications
    Notification.objects.get_or_create(incident=incident,audience='crew',context_key='offer:'+str(assignment.id),defaults={'recipient_team':team})
    enqueue_notifications(incident)
    audit(actor, 'crew.offered', incident, assignment_id=str(assignment.id))
    return assignment


@transaction.atomic
def assignment_transition(actor, pk, assignment_id, target, reason=''):
    incident = lock_incident(pk)
    from .access import require_active_adult
    require_active_adult(actor)
    assignment = Assignment.objects.select_for_update().select_related('team').get(pk=assignment_id, incident=incident)
    if is_device(actor) or not assignment.team.members.filter(pk=actor.pk).exists():
        raise PermissionDenied('Offered/assigned team member required.')
    allowed = {'offered': {'accepted', 'declined'}, 'accepted': {'en_route'}, 'en_route': {'arrived'}, 'arrived': {'complete'}}
    if incident.state not in OPEN_STATES or target not in allowed.get(assignment.state, set()):
        raise ValidationError('Invalid assignment transition.')
    if assignment.state == 'offered' and assignment.deadline <= timezone.now():
        raise ValidationError('Offer expired; coordinator must review.')
    if target == 'declined' and not reason.strip():
        raise ValidationError('A decline reason is required for coordinator review.')
    if target == 'accepted':
        team = Team.objects.select_for_update().get(pk=assignment.team_id)
        if not team.available or not team.on_duty:
            raise ValidationError('Team unavailable.')
        team.available = False
        team.save(update_fields=['available'])
        incident.state = 'active'
        incident.save(update_fields=['state'])
    if target == 'declined':
        from .workflow import escalate
        escalate(incident, 'crew_declined', 'assignment:'+str(assignment.id))
        incident.review_required = True
        incident.save(update_fields=['review_required'])
    assignment.state = target
    if target == 'declined':
        assignment.decline_reason = reason
    assignment.save(update_fields=['state', 'decline_reason'])
    audit(actor, 'crew.transition', incident, assignment_id=str(assignment.id), target=target)
    # Completion does not automatically declare team available; operations must verify.
    return assignment


@transaction.atomic
def record_ems(actor, pk, state, evidence, event_id=None, observed_at=None):
    incident = lock_incident(pk)
    require_coordinator(actor, incident)
    if incident.state not in OPEN_STATES or not evidence.strip():
        raise ValidationError('Open incident and evidence required.')
    operation = incident.ems
    from .models import EMSEvidenceEvent
    event_id=event_id or uuid.uuid4()
    fingerprint=hashlib.sha256(json.dumps({'state':state,'evidence':evidence,'observed_at':observed_at.isoformat() if observed_at else None},sort_keys=True).encode()).hexdigest()
    previous=EMSEvidenceEvent.objects.filter(operation=operation,event_id=event_id).first()
    if previous:
        if previous.fingerprint!=fingerprint:raise ValidationError('EMS evidence event ID reused with different data.')
        return operation
    allowed = {
        'handoff_pending': {'contact_confirmed', 'unknown', 'closed'},
        'provider_acknowledged': {'contact_confirmed', 'unknown', 'closed'},
        'unknown': {'contact_confirmed', 'closed'},
        'contact_confirmed': {'dispatch_confirmed', 'no_dispatch', 'closed'},
        'dispatch_confirmed': {'arrived', 'closed'}, 'arrived': {'closed'}, 'no_dispatch': {'closed'},
    }
    if state not in allowed.get(operation.state, set()):
        raise ValidationError('Invalid EMS evidence transition.')
    EMSEvidenceEvent.objects.create(operation=operation,event_id=event_id,fingerprint=fingerprint,state=state,evidence=evidence,observed_at=observed_at or timezone.now(),actor=actor)
    operation.state = state
    operation.evidence = evidence
    operation.save()
    incident.response_started_at = incident.response_started_at or timezone.now()
    incident.save(update_fields=['response_started_at'])
    if state=='unknown':
        from .workflow import escalate
        escalate(incident,'ems_unknown','ems:'+str(operation.id))
    audit(actor, 'ems.evidence_recorded', incident, state=state)
    return operation


class CapacityUnavailable(ValidationError):
    default_detail='No capacity; coordinator must arrange alternatives.'
    default_code='capacity_unavailable'


def reserve_placement(actor, pk, facility_id, authority_reference, suitability_confirmed, authority=None, care_place=None):
    try:
        return _reserve_placement(actor,pk,facility_id,authority_reference,suitability_confirmed,authority,care_place)
    except CapacityUnavailable:
        from .workflow import escalate
        with transaction.atomic():
            incident=lock_incident(pk);require_coordinator(actor,incident)
            escalate(incident,'care_capacity','care-capacity:'+str(pk)+':'+str(facility_id))
        raise


@transaction.atomic
def _reserve_placement(actor,pk,facility_id,authority_reference,suitability_confirmed,authority=None,care_place=None):
    from .care import approved_authority
    from operations.models import CarePlace
    incident=lock_incident(pk);require_coordinator(actor,incident)
    facility=Facility.objects.select_for_update().filter(pk=facility_id,region_id=incident.region_id,enabled=True).first()
    if incident.state not in ['triage','active'] or not facility or not authority_reference.strip() or not suitability_confirmed:
        raise ValidationError('Triage, suitable facility and verified authority reference required.')
    proof=approved_authority(incident.child_id,'placement',authority,authority_reference)
    if incident.placements.filter(state__in=['reserved','intake']).exists():raise ValidationError('Incident already has a live placement.')
    if Placement.objects.filter(facility=facility,state__in=['reserved','intake']).count()>=facility.capacity:raise CapacityUnavailable()
    selected=None
    if care_place:
        selected=CarePlace.objects.select_for_update().filter(pk=care_place,facility=facility,enabled=True).first()
        if not selected:raise ValidationError('Enabled place in selected facility required.')
        if Placement.objects.filter(care_place=selected,state__in=['reserved','intake']).exists():raise CapacityUnavailable()
    elif facility.places.filter(enabled=True).exists():
        occupied=Placement.objects.filter(facility=facility,state__in=['reserved','intake'],care_place__isnull=False).values('care_place_id')
        selected=facility.places.select_for_update().filter(enabled=True).exclude(pk__in=occupied).order_by('label').first()
        if not selected:raise CapacityUnavailable()
    placement=Placement.objects.create(incident=incident,facility=facility,authority_reference=authority_reference,authority=proof,care_place=selected,
        reserved_until=timezone.now()+timedelta(seconds=facility.reservation_seconds) if facility.reservation_seconds else None)
    incident.response_started_at=incident.response_started_at or timezone.now();incident.save(update_fields=['response_started_at'])
    audit(actor,'placement.reserved',incident,placement_id=str(placement.id),authority_id=str(proof.id))
    return placement


def placement_transition(actor,pk,placement_id,target,handover_reference,recipient=None,authority=None,transport_reference='',intake_reference='',belongings=None):
    from .care import transition_care
    return transition_care(actor,pk,placement_id,target,handover_reference,recipient,authority,transport_reference,intake_reference,belongings)


def process_simulated_work(limit=100):
    from .workflow import process_notification_jobs
    processed = process_notification_jobs(limit=limit)
    # Keep independent EMS and crew work progressing even if a notification
    # fails/blocks. Each incident has a short transaction; no global batch lock.
    incident_ids = list(Incident.objects.filter(state__in=OPEN_STATES).order_by('id').values_list('id', flat=True))
    for pk in incident_ids:
        _process_incident_tasks(pk)
    return processed


@transaction.atomic
def _process_incident_tasks(pk):
    from .workflow import escalate
    incident = lock_incident(pk)
    if incident.state not in OPEN_STATES:
        return
    operation = EMSOperation.objects.select_for_update().get(incident=incident)
    if operation.state == 'handoff_pending' and incident.region and incident.region.ems_mode == 'simulated':
        # This adapter is local and has no external side effect. EMS unknown
        # outcomes still stop for human reconciliation rather than auto-retry.
        try:
            result = SimulatedEMS().submit(operation.id)
            operation.state, operation.evidence = result.state, result.evidence
        except TimeoutError:
            operation.state, operation.evidence = 'unknown', 'SIMULATION: timeout; reconcile before retry'
        operation.save()
        incident.response_started_at = incident.response_started_at or timezone.now()
        incident.save(update_fields=['response_started_at'])
        if operation.state=='unknown':escalate(incident,'ems_unknown','ems:'+str(operation.id))
        audit(None, 'ems.simulated', incident, state=operation.state)
    for offer in Assignment.objects.select_for_update().filter(incident=incident, state='offered', deadline__lte=timezone.now()):
        offer.state = 'timed_out'
        offer.save(update_fields=['state'])
        escalate(incident, 'crew_timed_out', 'assignment:'+str(offer.id))
        audit(None, 'crew.offer_timed_out', incident)
    from .care import expire_reservations
    expire_reservations(incident.id)
    from .response_policy import tick_response_policy
    tick_response_policy(incident.id)


def continuation_status(incident):
    if incident.state not in OPEN_STATES:
        return 'closed'
    current = Entitlement.objects.filter(household_id=incident.child.household_id).first()
    if current and current.eligible(timezone.now()):
        return 'accepted'
    return 'continue_accepted_incident' if settings.CONTINUE_ACCEPTED_INCIDENTS else 'policy_review_required'


@transaction.atomic
def claim_ownership(actor, pk, takeover_reason=''):
    incident = lock_incident(pk)
    require_coordinator(actor, incident)
    if incident.state not in OPEN_STATES:
        raise ValidationError('Cannot claim a closed incident.')
    if incident.coordinator_owner_id and incident.coordinator_owner_id != actor.pk and not takeover_reason.strip():
        raise ValidationError('Explicit takeover reason required.')
    previous_owner_id = incident.coordinator_owner_id
    incident.coordinator_owner = actor
    if takeover_reason.strip():
        from .models import ProgressNote
        ProgressNote.objects.create(incident=incident, author=actor, action_taken='Ownership takeover: '+takeover_reason, next_steps='Continue accountable response and verify handover/disposition.')
    if incident.state == 'received':
        incident.state = 'triage'
    incident.save(update_fields=['coordinator_owner', 'state'])
    audit(actor, 'incident.ownership_acknowledged', incident, previous_owner_id=previous_owner_id)
    return incident


@transaction.atomic
def record_progress(actor, pk, action_taken, next_steps, review_completed=False):
    from .models import ProgressNote
    incident = lock_incident(pk)
    require_coordinator(actor, incident)
    if incident.coordinator_owner_id != actor.pk or incident.state not in OPEN_STATES:
        raise PermissionDenied('Current acknowledged coordinator owner required.')
    if not action_taken.strip() or not next_steps.strip():
        raise ValidationError('Action taken and next steps are required.')
    note = ProgressNote.objects.create(incident=incident, author=actor, action_taken=action_taken, next_steps=next_steps)
    if review_completed:
        incident.review_required = False
        incident.save(update_fields=['review_required'])
    audit(actor, 'incident.progress_recorded', incident, note_id=str(note.id), review_completed=review_completed)
    return note


@transaction.atomic
def acknowledge_notification(actor, pk, audience):
    incident = lock_incident(pk)
    if audience == 'guardian':
        require_guardian(actor, incident.child.household_id)
    else:
        require_coordinator(actor, incident)
    notification = Notification.objects.select_for_update().get(incident=incident, audience=audience,context_key='')
    if not notification.acknowledged_at:
        notification.acknowledged_at = timezone.now()
        notification.acknowledged_by = actor
        notification.save(update_fields=['acknowledged_at','acknowledged_by'])
        audit(actor, 'notification.acknowledged', incident, audience=audience)
    return notification


def public_status(incident):
    """Reassurance is tied to recorded facts; no estimates or EMS promises."""
    if incident.state == 'resolved':
        return {'code':'resolved', 'message':'Response completed after coordinator review.'}
    if incident.state == 'cancelled':
        return {'code':'cancelled', 'message':'Request closed after coordinator review.'}
    assignment = incident.assignments.order_by('-created_at').first()
    messages = {
        'offered': ('contacting_response_team', 'We are contacting a response team.'),
        'accepted': ('team_assigned', 'A response team has accepted your request.'),
        'en_route': ('team_en_route', 'Your response team is on the way.'),
        'arrived': ('team_arrived', 'Your response team has arrived.'),
    }
    if assignment and assignment.state in messages:
        code,message = messages[assignment.state]
        return {'code':code,'message':message}
    if incident.coordinator_owner_id:
        return {'code':'coordinator_review','message':'A coordinator is working on your request.'}
    return {'code':'request_received','message':'Your request was received.'}
