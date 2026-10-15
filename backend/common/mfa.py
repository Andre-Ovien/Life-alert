"""Local TOTP enrollment and per-session staff step-up; no delivery provider."""
import base64
import hashlib
import secrets
from datetime import timedelta
import pyotp
from cryptography.fernet import Fernet
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import BasePermission
from families.access import is_device
from .audit import audit
from .identity import digest
from .models import AdultTokenSession, StaffMFA


def cipher():
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(('life-alert-totp:'+settings.SECRET_KEY).encode()).digest()))


def privileged(user):
    from operations.models import Coordinator, Team, FacilityStaff
    return (user.is_superuser or user.is_staff or user.has_perm('common.review_privacyrequest')
        or user.has_perm('common.read_audit_events') or Coordinator.objects.filter(user=user).exists()
        or Team.objects.filter(members=user).exists() or FacilityStaff.objects.filter(user=user).exists())


class StaffMFAPermission(BasePermission):
    message = 'Staff MFA enrollment and verification are required for this session.'
    def has_permission(self, request, view):
        user=request.user
        if not settings.ENFORCE_STAFF_MFA or not user.is_authenticated or is_device(user) or not privileged(user):
            return True
        record=StaffMFA.objects.filter(user=user,confirmed_at__isnull=False).first()
        stamp=(request.auth.mfa_verified_at if isinstance(request.auth,AdultTokenSession)
               else request.session.get('staff_mfa_verified_at'))
        if isinstance(stamp,str):
            from django.utils.dateparse import parse_datetime
            stamp=parse_datetime(stamp)
        return bool(record and stamp and stamp>=record.confirmed_at and
                    stamp+timedelta(seconds=settings.STAFF_MFA_SECONDS)>timezone.now())


def adult(user):
    if is_device(user):raise PermissionDenied('Adult account required.')


@transaction.atomic
def enroll(user,password):
    adult(user)
    user=get_user_model().objects.select_for_update(no_key=True).get(pk=user.pk)
    if not user.check_password(password):raise PermissionDenied('Password reauthentication failed.')
    existing=StaffMFA.objects.filter(user=user).first()
    if existing and existing.confirmed_at:raise ValidationError('MFA is already enrolled; replacing it requires authenticated disable first.')
    secret=pyotp.random_base32()
    record,_=StaffMFA.objects.update_or_create(user=user,defaults={'encrypted_secret':cipher().encrypt(secret.encode()).decode(),
        'enrollment_expires_at':timezone.now()+timedelta(seconds=settings.STAFF_MFA_ENROLL_SECONDS),'last_step':-1,'recovery_digests':[]})
    audit(user,'identity.mfa_enrollment_started',record)
    return {'secret':secret,'provisioning_uri':pyotp.TOTP(secret).provisioning_uri(name=user.username,issuer_name='Life alert'),
        'expires_at':record.enrollment_expires_at}


def consume_factor(record,code,at,allow_recovery=True):
    # No clock grace: an accepted counter is consumed under the user lock.
    totp=pyotp.TOTP(cipher().decrypt(record.encrypted_secret.encode()).decode())
    step=int(at.timestamp())//totp.interval
    if step>record.last_step and totp.verify(code,for_time=at,valid_window=0):
        record.last_step=step
    elif allow_recovery and digest(code) in record.recovery_digests:
        record.recovery_digests.remove(digest(code))
    else:raise ValidationError('Invalid, expired or already used MFA code.')


@transaction.atomic
def verify(request,code,confirm=False):
    adult(request.user)
    get_user_model().objects.select_for_update(no_key=True).get(pk=request.user.pk)
    record=StaffMFA.objects.select_for_update().filter(user=request.user).first()
    at=timezone.now()
    if not record:raise ValidationError('MFA enrollment required.')
    if confirm:
        if record.confirmed_at or record.enrollment_expires_at<=at:raise ValidationError('Pending, unexpired enrollment required.')
    elif not record.confirmed_at:raise ValidationError('Confirm enrollment first.')
    consume_factor(record,code,at,allow_recovery=not confirm)
    recovery=[]
    if confirm:
        record.confirmed_at=at
        recovery=[secrets.token_hex(12) for _ in range(8)]
        record.recovery_digests=[digest(item) for item in recovery]
    record.save()
    if isinstance(request.auth,AdultTokenSession):
        # Do not revive a session revoked concurrently by logout/recovery.
        session=AdultTokenSession.objects.select_for_update().get(pk=request.auth.pk)
        if session.revoked_at or session.access_expires_at<=at:raise PermissionDenied('Current session is unavailable.')
        session.mfa_verified_at=at;session.save(update_fields=['mfa_verified_at'])
    else:request.session['staff_mfa_verified_at']=at.isoformat()
    audit(request.user,'identity.mfa_confirmed' if confirm else 'identity.mfa_verified',record)
    result={'verified':True,'valid_until':at+timedelta(seconds=settings.STAFF_MFA_SECONDS)}
    if confirm:result['recovery_codes']=recovery
    return result


@transaction.atomic
def disable(user,password,code):
    adult(user)
    user=get_user_model().objects.select_for_update(no_key=True).get(pk=user.pk)
    if not user.check_password(password):raise PermissionDenied('Password reauthentication failed.')
    record=StaffMFA.objects.select_for_update().filter(user=user,confirmed_at__isnull=False).first()
    if not record:raise ValidationError('Confirmed enrollment required.')
    consume_factor(record,code,timezone.now())
    audit(user,'identity.mfa_disabled',record)
    record.delete()
