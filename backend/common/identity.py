"""First-party opaque mobile tokens and simulated identity-delivery contracts.

No SMS/email is sent; no identity/legal verification claim follows contact proof.
"""
import hashlib
import secrets
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from common.audit import audit
from .models import (AdultTokenSession,UsedRefreshToken,AccountChallenge,VerifiedContact,IdentityDispatch)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def _credentials(session):
    access,refresh=secrets.token_urlsafe(32),secrets.token_urlsafe(48)
    session.access_digest,session.refresh_digest=digest(access),digest(refresh)
    session.access_expires_at=timezone.now()+timedelta(seconds=settings.ADULT_ACCESS_SECONDS)
    session.save()
    return {'access_token':access,'refresh_token':refresh,'token_type':'Bearer',
        'access_expires_at':session.access_expires_at,'refresh_expires_at':session.refresh_expires_at}


@transaction.atomic
def issue_tokens(username,password,request=None):
    user=authenticate(request=request,username=username,password=password)
    if not user:raise AuthenticationFailed('Invalid credentials or unavailable account.')
    user=get_user_model().objects.select_for_update(no_key=True).get(pk=user.pk)
    if not user.is_active:raise AuthenticationFailed('Account is unavailable.')
    if settings.REQUIRE_VERIFIED_ADULT_CONTACT and not VerifiedContact.objects.filter(user=user,email=user.email).exists():
        raise AuthenticationFailed('Contact verification is required before mobile sign-in.')
    # Initial digests are independent random values, replaced by _credentials.
    session=AdultTokenSession(user=user,access_digest=digest(secrets.token_urlsafe(32)),refresh_digest=digest(secrets.token_urlsafe(32)),
        access_expires_at=timezone.now(),refresh_expires_at=timezone.now()+timedelta(seconds=settings.ADULT_REFRESH_SECONDS))
    result=_credentials(session)
    audit(user,'identity.mobile_session_issued',session)
    return result


def refresh_tokens(raw):
    value=digest(raw)
    candidate=AdultTokenSession.objects.filter(refresh_digest=value).first()
    reused=UsedRefreshToken.objects.filter(digest=value).select_related('session').first()
    if not candidate and not reused:raise AuthenticationFailed('Invalid refresh credential.')
    pk=candidate.pk if candidate else reused.session_id
    invalid=False;result=None
    with transaction.atomic():
        user_id=(candidate.user_id if candidate else reused.session.user_id)
        get_user_model().objects.select_for_update(no_key=True).get(pk=user_id)
        session=AdultTokenSession.objects.select_for_update(of=('self',)).select_related('user').get(pk=pk)
        if session.refresh_digest!=value:
            session.revoked_at=timezone.now();session.save(update_fields=['revoked_at'])
            audit(session.user,'identity.refresh_replay_revoked',session)
            invalid=True
        elif session.revoked_at or session.refresh_expires_at<=timezone.now() or not session.user.is_active:
            invalid=True
        else:
            UsedRefreshToken.objects.create(session=session,digest=value)
            result=_credentials(session)
            audit(session.user,'identity.mobile_session_rotated',session)
    # Raise after committing revocation so rollback cannot undo replay protection.
    if invalid:raise AuthenticationFailed('Invalid, replayed or expired refresh credential.')
    return result


class AdultBearerAuthentication(BaseAuthentication):
    def authenticate_header(self,request):return 'Bearer'
    def authenticate(self,request):
        header=request.headers.get('Authorization','')
        if not header.startswith('Bearer '):return None
        token=header[7:]
        if not 20<=len(token)<=200:raise AuthenticationFailed('Invalid access credential.')
        session=AdultTokenSession.objects.select_related('user').filter(access_digest=digest(token),revoked_at__isnull=True,
            access_expires_at__gt=timezone.now(),refresh_expires_at__gt=timezone.now()).first()
        if not session or not session.user.is_active:raise AuthenticationFailed('Invalid or expired access credential.')
        return session.user,session


@transaction.atomic
def revoke_sessions(actor,session=None):
    get_user_model().objects.select_for_update(no_key=True).get(pk=actor.pk)
    query=AdultTokenSession.objects.filter(user=actor,revoked_at__isnull=True)
    if session:query=query.filter(pk=session.pk)
    for item in query.select_for_update():
        item.revoked_at=timezone.now();item.save(update_fields=['revoked_at'])
        audit(actor,'identity.mobile_session_revoked',item)


class SimulatedIdentityDelivery:
    def deliver(self,challenge,token):
        # Token intentionally not persisted/logged/returned by public APIs.
        IdentityDispatch.objects.get_or_create(challenge=challenge)
        return 'simulated'


def create_challenge(user,purpose,email):
    raw=secrets.token_urlsafe(32)
    with transaction.atomic():
        challenge=AccountChallenge.objects.create(user=user,purpose=purpose,target_email=email,
            digest=digest(raw),expires_at=timezone.now()+timedelta(seconds=settings.ACCOUNT_CHALLENGE_SECONDS))
        audit(user,'identity.challenge_created',challenge,purpose=purpose)
    SimulatedIdentityDelivery().deliver(challenge,raw)
    return challenge


def request_recovery(username):
    user=get_user_model().objects.filter(username=username,is_active=True).first()
    if user and VerifiedContact.objects.filter(user=user,email=user.email).exists():
        create_challenge(user,'recovery',user.email)
    # Same public response whether or not an eligible account exists.


@transaction.atomic
def consume_challenge(raw,purpose,new_password=None):
    from django.core.exceptions import ValidationError as DjangoValidationError
    challenge=AccountChallenge.objects.select_for_update().filter(digest=digest(raw),purpose=purpose).first()
    if not challenge or challenge.used_at or challenge.expires_at<=timezone.now():
        raise ValidationError('Invalid, used or expired account challenge.')
    user=get_user_model().objects.select_for_update(no_key=True).get(pk=challenge.user_id)
    if not user.is_active:raise ValidationError('Account is unavailable.')
    if purpose=='recovery':
        if not isinstance(new_password,str):raise ValidationError({'new_password':'Required.'})
        try:validate_password(new_password,user=user)
        except DjangoValidationError as exc:raise ValidationError({'new_password':exc.messages})
        user.set_password(new_password);user.save(update_fields=['password'])
        revoke_sessions(user)
    else:
        user.email=challenge.target_email;user.save(update_fields=['email'])
        VerifiedContact.objects.update_or_create(user=user,email=user.email,defaults={'verified_at':timezone.now()})
    challenge.used_at=timezone.now();challenge.save(update_fields=['used_at'])
    audit(user,'identity.challenge_consumed',challenge,purpose=purpose)
    return user
