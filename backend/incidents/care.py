"""Protected operational assertions; legal/physical verification is external."""
import hashlib,json,uuid
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied,ValidationError
from common.audit import audit
from families.access import is_device
from families.models import AuthorityRecord
from operations.models import FacilityStaff
from .access import coordinator
from .models import Incident,Placement,CareHandover,CareEvent,OPEN_STATES


def approved_authority(child_id,purpose,pk=None,reference=None,subject=None):
    query=AuthorityRecord.objects.filter(child_id=child_id,purpose=purpose,status='verified',
        valid_until__gt=timezone.now(),verified_by__isnull=False,subject__is_active=True).exclude(verification_reference='')
    if pk:query=query.filter(pk=pk)
    elif reference:query=query.filter(evidence_reference=reference)
    else:raise ValidationError('Recorded, current reviewed care authority is required.')
    if subject is not None:query=query.filter(subject_id=subject)
    obj=query.order_by('-created_at').first()
    if not obj:raise ValidationError('Recorded, current reviewed care authority is required.')
    return obj


def valid_staff(user_id,facility_id):
    return FacilityStaff.objects.filter(user_id=user_id,facility_id=facility_id,active=True,on_duty=True,user__is_active=True).exclude(review_reference='').exists()


def require_staff_or_coordinator(actor,placement,write=False):
    if write:
        from .access import require_active_adult
        require_active_adult(actor)
    if coordinator(actor,placement.incident):
        if write and placement.incident.coordinator_owner_id!=actor.pk:raise PermissionDenied('Claim incident ownership before changing care responsibility.')
        return
    if is_device(actor) or not placement.staff.filter(pk=actor.pk).exists() or not valid_staff(actor.pk,placement.facility_id):
        raise PermissionDenied('Regional coordinator or assigned authorized care staff required.')
    if write and placement.current_staff_id!=actor.pk:
        raise PermissionDenied('Current accountable care staff required.')


def lock_placement(pk):
    incident_id=Placement.objects.values_list('incident_id',flat=True).get(pk=pk)
    Incident.objects.select_for_update().get(pk=incident_id)
    return Placement.objects.select_for_update(of=('self',)).select_related('incident','facility').get(pk=pk)


@transaction.atomic
def assign_staff(actor,pk,recipient,reference):
    placement=lock_placement(pk);require_staff_or_coordinator(actor,placement,write=True)
    if placement.state not in ['reserved','intake'] or not reference.strip():raise ValidationError('Open care placement and handover reference required.')
    if not valid_staff(recipient.id,placement.facility_id):raise ValidationError('Reviewed active on-duty facility staff required.')
    if placement.handovers.filter(status='pending').exists():raise ValidationError('A care handover is already pending.')
    placement.staff.add(recipient)
    handover=CareHandover.objects.create(placement=placement,kind='shift' if placement.state=='intake' else 'intake',
        source_id=placement.current_staff_id,recipient=recipient,author=actor,reference=reference)
    audit(actor,'care.staff_handover_requested',placement,handover_id=str(handover.id))
    return handover


@transaction.atomic
def accept_staff_handover(actor,pk,handover_id):
    placement=lock_placement(pk)
    handover=CareHandover.objects.select_for_update().get(pk=handover_id,placement=placement)
    from .access import require_active_adult
    require_active_adult(actor)
    if is_device(actor) or actor.pk!=handover.recipient_id or not valid_staff(actor.pk,placement.facility_id):raise PermissionDenied('Named receiving authorized staff required.')
    if placement.state not in ['reserved','intake'] or handover.status!='pending' or handover.source_id!=placement.current_staff_id:
        raise ValidationError('Handover is stale or no longer pending.')
    handover.status='accepted';handover.accepted_at=timezone.now();handover.save(update_fields=['status','accepted_at'])
    if handover.source_id and handover.source_id!=actor.pk:placement.staff.remove(handover.source_id)
    placement.current_staff=actor;placement.save(update_fields=['current_staff'])
    audit(actor,'care.staff_handover_accepted',placement,handover_id=str(handover.id))
    return handover


@transaction.atomic
def record_care_event(actor,pk,event_id,kind,note):
    placement=lock_placement(pk);require_staff_or_coordinator(actor,placement,write=True)
    if placement.state!='intake' or kind not in ['support','observation','handover_note'] or not note.strip():raise ValidationError('Active intake and a supported care record are required.')
    fingerprint=hashlib.sha256(json.dumps({'kind':kind,'note':note},sort_keys=True).encode()).hexdigest()
    existing=CareEvent.objects.filter(placement=placement,event_id=event_id).first()
    if existing:
        if existing.fingerprint!=fingerprint:raise ValidationError('Care event ID reused with different data.')
        return existing
    event=CareEvent.objects.create(placement=placement,event_id=event_id,author=actor,kind=kind,note=note,fingerprint=fingerprint)
    audit(actor,'care.event_recorded',placement,event_id=str(event.id),kind=kind)
    return event


@transaction.atomic
def transition_care(actor,incident_id,placement_id,target,reference,recipient=None,authority=None,transport_reference='',intake_reference='',belongings=None):
    placement=lock_placement(placement_id)
    if placement.incident_id!=incident_id:raise ValidationError('Placement does not belong to incident.')
    require_staff_or_coordinator(actor,placement,write=True)
    allowed={'reserved':{'intake','cancelled'},'intake':{'released'}}
    if placement.incident.state not in OPEN_STATES or target not in allowed.get(placement.state,set()) or not reference.strip():raise ValidationError('Valid transition and reviewed handover reference required.')
    if target=='intake':
        if placement.reserved_until and placement.reserved_until<=timezone.now():raise ValidationError('Reservation expired; arrange a reviewed alternative.')
        if not placement.current_staff_id or not valid_staff(placement.current_staff_id,placement.facility_id):raise ValidationError('Receiving care staff must explicitly accept responsibility before intake.')
        approved_authority(placement.incident.child_id,'placement',placement.authority_id)
        if not transport_reference.strip() or not intake_reference.strip():raise ValidationError('Transport and structured intake references required.')
        placement.intake_at=timezone.now()
        placement.transport_reference=transport_reference;placement.intake_reference=intake_reference
        placement.belongings=belongings or []
    if target=='released':
        placement.released_at=timezone.now()
        if placement.handovers.filter(status='pending').exists():raise ValidationError('Reconcile pending staff handover before release.')
        if not recipient:raise ValidationError('Verified release recipient and authority required.')
        proof=approved_authority(placement.incident.child_id,'release',authority,subject=recipient.pk)
        CareHandover.objects.create(placement=placement,kind='release',source_id=placement.current_staff_id,recipient=recipient,
            author=actor,status='accepted',accepted_at=timezone.now(),reference=reference,authority=proof)
    if target=='cancelled':
        placement.handovers.filter(status='pending').update(status='cancelled')
    placement.state=target;placement.handover_reference=reference;placement.save()
    audit(actor,'placement.transition',placement.incident,placement_id=str(placement.id),target=target)
    return placement


@transaction.atomic
def expire_reservations(incident_id,at=None):
    from .workflow import escalate
    Incident.objects.select_for_update().get(pk=incident_id)
    at=at or timezone.now()
    for placement in Placement.objects.select_for_update().filter(incident_id=incident_id,state='reserved',reserved_until__lte=at):
        placement.state='cancelled';placement.handover_reference='Reservation expired before intake';placement.save()
        placement.handovers.filter(status='pending').update(status='cancelled')
        escalate(placement.incident,'reservation_expired','reservation:'+str(placement.id))
        audit(None,'care.reservation_expired',placement.incident,placement_id=str(placement.id))


@transaction.atomic
def end_staff_handover(actor,pk,handover_id,target,reference):
    placement=lock_placement(pk)
    handover=CareHandover.objects.select_for_update().get(pk=handover_id,placement=placement)
    if is_device(actor):raise PermissionDenied()
    if target=='declined':
        if actor.pk!=handover.recipient_id:raise PermissionDenied('Named receiving staff required.')
    elif target=='cancelled':require_staff_or_coordinator(actor,placement,write=True)
    else:raise ValidationError('Unsupported handover decision.')
    if handover.status!='pending' or not reference.strip():raise ValidationError('Pending handover and decision reference required.')
    handover.status=target;handover.save(update_fields=['status'])
    if placement.current_staff_id!=handover.recipient_id:placement.staff.remove(handover.recipient)
    # Preserve the decision reference without overwriting the original agreement.
    CareEvent.objects.create(placement=placement,event_id=uuid.uuid4(),author=actor,
        kind='handover_note',note='Handover '+target+': '+reference,
        fingerprint=hashlib.sha256(reference.encode()).hexdigest())
    from .workflow import escalate
    if target=='declined':escalate(placement.incident,'care_handover','handover:'+str(handover.id))
    audit(actor,'care.staff_handover_'+target,placement,handover_id=str(handover.id))
    return handover
