import hashlib
import secrets
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from common.audit import audit
from .access import require_guardian, require_child_access, is_device, PERMISSIONS
from .models import (Child, Household, CareVersion, CaregiverGrant,
                     CaregiverInvitation, SavedPlace)


def lock_child(pk):
    child = Child.objects.get(pk=pk)
    Household.objects.select_for_update().get(pk=child.household_id)
    return Child.objects.select_for_update().get(pk=pk)


def capture_version(child, actor):
    # Called under household/child lock, including incident acceptance.
    child.current_version += 1
    child.updated_by = None if is_device(actor) else actor
    child.save(update_fields=['current_version','updated_by','updated_at'])
    payload = {k:getattr(child,k) for k in ['name','communication','support_needs','calming_preferences','saved_address']}
    payload['contacts'] = list(child.contacts.filter(active=True).values('name','phone','relationship'))
    payload['places'] = list(child.places.filter(active=True).values('label','address','is_default'))
    version = CareVersion.objects.create(child=child, number=child.current_version, payload=payload, author=child.updated_by)
    audit(actor, 'care.version_created', child, version=version.number)
    return version


@transaction.atomic
def ensure_version(child_id, actor):
    child = lock_child(child_id)
    existing = child.care_versions.filter(number=child.current_version).first()
    return existing or capture_version(child, actor)


@transaction.atomic
def update_profile(actor, child_id, values, expected_version):
    child = lock_child(child_id)
    require_child_access(actor, child, 'manage_profile')
    if expected_version is None or expected_version != child.current_version:
        raise ValidationError({'expected_version':'Profile changed; reload and review the current care version.'})
    allowed = {'name','communication','support_needs','calming_preferences','saved_address'}
    if set(values)-allowed:
        raise ValidationError('Unsupported profile field.')
    for key,value in values.items():setattr(child,key,value)
    child.save()
    capture_version(child, actor)
    audit(actor, 'child.updated', child)
    return child


@transaction.atomic
def invite_caregiver(actor, child_id, recipient, relationship, permissions):
    child = lock_child(child_id)
    require_guardian(actor, child.household_id)
    if is_device(actor) or not set(permissions)<=PERMISSIONS or not permissions:
        raise ValidationError('Choose explicit supported permissions.')
    if ('request_help' in permissions and 'view_incidents' not in permissions) or (set(permissions)&{'manage_profile','manage_media','manage_devices'} and 'view_care' not in permissions):
        raise ValidationError('Editing requires explicit view_care; help requires explicit view_incidents.')
    if recipient == actor or not recipient.is_active:
        raise ValidationError('An active, separate recipient account is required.')
    token = secrets.token_urlsafe(32)
    invite = CaregiverInvitation.objects.create(child=child, inviter=actor, recipient=recipient,
        relationship=relationship, permissions=sorted(set(permissions)),
        token_digest=hashlib.sha256(token.encode()).hexdigest(),
        expires_at=timezone.now()+timedelta(seconds=settings.CAREGIVER_INVITE_SECONDS))
    audit(actor, 'caregiver.invited', invite, child_id=str(child.id))
    return invite, token  # Manual/sandbox sharing only; no email/SMS sent.


@transaction.atomic
def accept_invitation(actor, token, accept=True):
    if is_device(actor):raise PermissionDenied('Adult recipient required.')
    digest = hashlib.sha256(token.encode()).hexdigest()
    invite = CaregiverInvitation.objects.get(token_digest=digest)
    child = lock_child(invite.child_id)
    invite = CaregiverInvitation.objects.select_for_update().get(pk=invite.id)
    if invite.recipient_id != actor.pk:raise PermissionDenied('Invitation belongs to another account.')
    if invite.status != 'pending' or invite.expires_at <= timezone.now():
        raise ValidationError('Invitation is expired, revoked or already used.')
    invite.status = 'accepted' if accept else 'declined';invite.save(update_fields=['status'])
    if accept:
        values = {'can_'+key:key in invite.permissions for key in PERMISSIONS}
        grant,_ = CaregiverGrant.objects.update_or_create(child=child,user=actor,
            defaults={**values,'relationship':invite.relationship,'revoked_at':None,'expires_at':None})
        audit(actor, 'caregiver.grant_accepted', grant)
    audit(actor, 'caregiver.invitation_consumed', invite, accepted=accept)
    return invite


@transaction.atomic
def revoke_grant(actor, pk):
    grant = CaregiverGrant.objects.get(pk=pk)
    child = lock_child(grant.child_id)
    require_guardian(actor,child.household_id)
    grant = CaregiverGrant.objects.select_for_update().get(pk=pk)
    grant.revoked_at = timezone.now();grant.save(update_fields=['revoked_at'])
    audit(actor, 'caregiver.revoked', grant)
    return grant


@transaction.atomic
def save_place(actor, child_id, values, place_id=None):
    child = lock_child(child_id);require_child_access(actor,child,'manage_profile')
    if values.get('is_default') and values.get('active',True):
        child.places.filter(is_default=True).update(is_default=False)
    if place_id:
        place = SavedPlace.objects.select_for_update().get(pk=place_id,child=child)
        for key,value in values.items():setattr(place,key,value)
        place.save()
    else:place = SavedPlace.objects.create(child=child,**values)
    default = child.places.filter(active=True,is_default=True).first()
    if default:
        child.saved_address=default.address;child.save(update_fields=['saved_address'])
    elif values.get('active') is False or values.get('is_default') is False:
        child.saved_address='';child.save(update_fields=['saved_address'])
    capture_version(child,actor)
    audit(actor,'place.updated' if place_id else 'place.created',place)
    return place
