"""Provider-independent local contracts. Billing ingestion is sandbox/admin only."""
import hashlib
import json
import secrets
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from common.audit import audit
from .access import require_child_access
from .services import lock_child
from .models import Device,DeviceLinkChallenge,Household,Entitlement,BillingEvent


def _digest(raw):return hashlib.sha256(raw.encode()).hexdigest()

def credential_expiry():
    return timezone.now()+timedelta(seconds=settings.DEVICE_TOKEN_SECONDS) if settings.DEVICE_TOKEN_SECONDS else None


@transaction.atomic
def start_pairing(actor,child_id,label):
    child=lock_child(child_id);require_child_access(actor,child,'manage_devices')
    raw=secrets.token_urlsafe(32)
    obj=DeviceLinkChallenge.objects.create(child=child,creator=actor,label=label,digest=_digest(raw),
        expires_at=timezone.now()+timedelta(seconds=settings.DEVICE_PAIRING_SECONDS))
    audit(actor,'device.pairing_started',obj)
    return obj,raw


@transaction.atomic
def consume_pairing(raw):
    obj=DeviceLinkChallenge.objects.get(digest=_digest(raw))
    child=lock_child(obj.child_id)
    obj=DeviceLinkChallenge.objects.select_for_update().select_related('creator').get(pk=obj.pk)
    if obj.consumed_at or obj.revoked_at or obj.expires_at<=timezone.now() or not obj.creator.is_active:
        raise ValidationError('Invalid, expired or used pairing challenge.')
    require_child_access(obj.creator,child,'manage_devices')
    token=secrets.token_urlsafe(32)
    device=Device.objects.create(child=child,label=obj.label,token_digest=_digest(token),expires_at=credential_expiry())
    obj.consumed_at=timezone.now();obj.save(update_fields=['consumed_at'])
    audit(obj.creator,'device.pairing_completed',device,challenge_id=str(obj.id))
    return device,token


@transaction.atomic
def revoke_pairing(actor,pk):
    obj=DeviceLinkChallenge.objects.get(pk=pk);child=lock_child(obj.child_id)
    require_child_access(actor,child,'manage_devices')
    obj=DeviceLinkChallenge.objects.select_for_update().get(pk=pk)
    obj.revoked_at=timezone.now();obj.save(update_fields=['revoked_at'])
    audit(actor,'device.pairing_revoked',obj)
    return obj


@transaction.atomic
def rotate_device(actor,pk):
    old=Device.objects.get(pk=pk);child=lock_child(old.child_id)
    require_child_access(actor,child,'manage_devices')
    old=Device.objects.select_for_update().get(pk=pk)
    if old.revoked_at:raise ValidationError('Device is revoked; create a new pairing instead.')
    raw=secrets.token_urlsafe(32)
    new=Device.objects.create(child=child,label=old.label,token_digest=_digest(raw),expires_at=credential_expiry(),rotated_from=old)
    old.revoked_at=timezone.now();old.save(update_fields=['revoked_at'])
    audit(actor,'device.credential_rotated',new,previous_device=str(old.id))
    return new,raw


@transaction.atomic
def apply_sandbox_billing_event(actor,household_id,event_id,revision,active,starts_at,ends_at):
    # No unauthenticated provider webhook exists. A real adapter must verify
    # signatures and normalize an authoritative per-household revision first.
    household=Household.objects.select_for_update().get(pk=household_id)
    if revision<1 or ends_at<=starts_at:raise ValidationError('Valid revision and time interval required.')
    payload={'household':str(household.id),'revision':revision,'active':active,'starts_at':starts_at.isoformat(),'ends_at':ends_at.isoformat()}
    fingerprint=_digest(json.dumps(payload,sort_keys=True))
    previous=BillingEvent.objects.filter(provider='sandbox',event_id=event_id).first()
    if previous:
        if previous.fingerprint!=fingerprint:raise ValidationError('Event ID reused with different normalized data.')
        return previous
    ledger=Entitlement.objects.select_for_update().filter(household=household).first()
    current=ledger.billing_revision if ledger else 0
    status='ignored' if revision<current else 'applied'
    if ledger and revision==current:
        status='ignored' if ledger.billing_fingerprint==fingerprint else 'conflict'
    event,created=BillingEvent.objects.get_or_create(provider='sandbox',event_id=event_id,
        defaults={'household':household,'revision':revision,'fingerprint':fingerprint,'status':status})
    if not created:
        if event.fingerprint!=fingerprint:raise ValidationError('Event ID reused with different normalized data.')
        return event
    if status=='applied':
        Entitlement.objects.update_or_create(household=household,defaults={'active':active,'starts_at':starts_at,'ends_at':ends_at,
            'source':'sandbox','billing_revision':revision,'billing_fingerprint':fingerprint})
    audit(actor,'billing.sandbox_event_recorded',event,status=status,revision=revision)
    return event
