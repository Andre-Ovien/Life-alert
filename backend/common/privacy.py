"""Purpose-scoped data requests. Unknown retention/legal policy fails closed."""
import hashlib,json
from datetime import timedelta
from django.core.files.storage import FileSystemStorage
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied,ValidationError
from families.access import is_device,require_guardian
from families.models import Child,CareMedia,Guardian,RetiredMediaBlob,Household
from common.audit import audit
from .models import PrivacyRequest,RetentionPolicy,PrivacyDecision


def require_privacy_reviewer(actor):
    if is_device(actor) or not actor.has_perm('common.review_privacyrequest'):
        raise PermissionDenied('Purpose-scoped privacy review permission required.')


@transaction.atomic
def submit_request(actor,request_id,kind,child_id=None,media_id=None,details=''):
    if is_device(actor):raise PermissionDenied('Adult requester required.')
    if kind not in ['export','correction','media_delete','account_close']:raise ValidationError('Unsupported privacy request.')
    child=Child.objects.get(pk=child_id) if child_id else None
    media=CareMedia.objects.get(pk=media_id) if media_id else None
    if media:
        if child and media.child_id!=child.id:raise ValidationError('Media child mismatch.')
        child=media.child
    if child:require_guardian(actor,child.household_id)
    if kind=='correction' and not child:raise ValidationError('Child-profile corrections require a child; adult contact changes use verified identity flow.')
    if kind=='media_delete' and not media:raise ValidationError('Media required.')
    if kind=='account_close' and (child or media):raise ValidationError('Account closure is an adult account request.')
    fingerprint=hashlib.sha256(json.dumps({'kind':kind,'child':str(child.id) if child else None,'media':str(media.id) if media else None,'details':details},sort_keys=True).encode()).hexdigest()
    obj,created=PrivacyRequest.objects.get_or_create(requester=actor,request_id=request_id,
        defaults={'kind':kind,'child':child,'media':media,'details':details,'fingerprint':fingerprint})
    if obj.fingerprint!=fingerprint:raise ValidationError('Privacy request ID reused with different data.')
    if created:audit(actor,'privacy.request_submitted',obj,kind=kind)
    return obj


@transaction.atomic
def review_request(actor,pk,target,reference):
    require_privacy_reviewer(actor)
    case=PrivacyRequest.objects.select_for_update().get(pk=pk)
    if case.status in ['fulfilled','denied'] or target not in ['approved','hold','denied'] or not reference.strip():
        raise ValidationError('Reviewable request, supported decision and reference required.')
    if case.child_id:require_guardian(case.requester,case.child.household_id)
    case.reviewer=actor;case.review_reference=reference;case.status=target
    if target=='approved' and case.kind=='media_delete':
        media=CareMedia.objects.select_for_update().get(pk=case.media_id)
        policy=RetentionPolicy.objects.filter(purpose='media',enabled=True,minimum_seconds__isnull=False).exclude(review_reference='').first()
        if media.legal_hold or not policy:
            case.status='hold'
        else:
            media.archived_at=timezone.now();media.save(update_fields=['archived_at'])
            bounds=[timezone.now()+timedelta(seconds=policy.minimum_seconds),media.retention_until or timezone.now()]
            bounds.extend(media.retiredmediablob_set.filter(purged_at__isnull=True,purge_after__isnull=False).values_list('purge_after',flat=True))
            case.purge_after=max(bounds)
            media.retiredmediablob_set.filter(purged_at__isnull=True,purge_after__isnull=True).update(purge_after=case.purge_after)
            case.status='processing'
    if target=='approved' and case.kind=='account_close':
        from incidents.models import Incident,OPEN_STATES
        user=case.requester
        households=list(Guardian.objects.filter(user=user).values_list('household_id',flat=True))
        # Serialize closure against new incident acceptance and profile creation.
        list(Household.objects.select_for_update().filter(pk__in=households).order_by('id'))
        from django.contrib.auth import get_user_model
        # Staff mutation guards take this same user lock before acquiring new duty.
        user=get_user_model().objects.select_for_update(no_key=True).get(pk=user.pk)
        from django.db.models import Q
        active_care=Incident.objects.filter(state__in=OPEN_STATES).filter(
            Q(child__household_id__in=households)|Q(coordinator_owner=user)|
            Q(assignments__team__members=user,assignments__state__in=['offered','accepted','en_route','arrived'])|
            Q(placements__staff=user,placements__state__in=['reserved','intake'])|
            Q(escalations__acknowledged_by=user,escalations__status='acknowledged')).exists()
        if active_care:
            case.status='hold'
        else:
            # Do not orphan a household with children by disabling its last adult.
            for guardian in Guardian.objects.filter(user=user).select_related('household'):
                if guardian.household.children.exists() and not Guardian.objects.filter(household=guardian.household,user__is_active=True).exclude(user=user).exists():
                    case.status='hold';break
            if case.status=='approved':
                from .identity import revoke_sessions
                revoke_sessions(user)
                user.is_active=False;user.save(update_fields=['is_active'])
                case.status='fulfilled'
    case.save()
    PrivacyDecision.objects.create(request=case,actor=actor,decision=case.status,reference=reference)
    audit(actor,'privacy.request_reviewed',case,status=case.status)
    return case


@transaction.atomic
def prepare_export(actor,pk):
    case=PrivacyRequest.objects.select_for_update().get(pk=pk)
    if is_device(actor) or case.requester_id!=actor.pk or case.kind!='export' or case.status not in ['approved','fulfilled']:
        raise PermissionDenied('Approved export for this requester required.')
    from families.models import CareVersion,EmergencyContact,SavedPlace
    payload={'scope':'Reviewed application records; not a claim of complete statutory disclosure',
        'account':{'username':actor.username,'email':actor.email},'audio_included':False}
    if case.child_id:
        child=case.child;require_guardian(actor,child.household_id)
        payload['child']={k:getattr(child,k) for k in ['name','communication','support_needs','calming_preferences','saved_address','current_version']}
        payload['contacts']=list(EmergencyContact.objects.filter(child=child).values('name','phone','relationship','active'))
        payload['places']=list(SavedPlace.objects.filter(child=child).values('label','address','active','is_default'))
        payload['care_versions']=list(CareVersion.objects.filter(child=child).order_by('number').values('number','payload'))
        payload['media_metadata']=list(CareMedia.objects.filter(child=child).values('title','for_child','for_responder','instructions_text'))
    payload['excluded_components']=['audio bytes','staff private identity/security records','credentials','provider raw records']
    case.status='fulfilled';case.save(update_fields=['status'])
    audit(actor,'privacy.export_prepared',case)
    return payload


def purge_media_due(at=None):
    at=at or timezone.now()
    policy=RetentionPolicy.objects.filter(purpose='media',enabled=True,minimum_seconds__isnull=False).exclude(review_reference='').first()
    if not policy:return 0
    count=0
    for pk in list(PrivacyRequest.objects.filter(kind='media_delete',status='processing',purge_after__lte=at).values_list('id',flat=True)):
        with transaction.atomic():
            if not RetentionPolicy.objects.select_for_update().filter(purpose='media',enabled=True,minimum_seconds__isnull=False).exclude(review_reference='').exists():return count
            case=PrivacyRequest.objects.select_for_update().get(pk=pk)
            if case.status!='processing':continue
            media=CareMedia.objects.select_for_update().get(pk=case.media_id)
            if media.legal_hold or (media.retention_until and media.retention_until>at):continue
            if not isinstance(media.file.storage,FileSystemStorage):
                continue  # No unreviewed cloud storage deletion adapter.
            for blob in RetiredMediaBlob.objects.select_for_update().filter(media=media,purged_at__isnull=True):
                if blob.purge_after and blob.purge_after>at:break
                media.file.storage.delete(blob.storage_name)
                blob.purged_at=at;blob.save(update_fields=['purged_at'])
            else:
                if media.file.name:media.file.storage.delete(media.file.name)
                media.file='';media.save(update_fields=['file'])
                case.status='fulfilled';case.save(update_fields=['status'])
                audit(None,'privacy.media_purged',case);count+=1
            continue
    for pk in list(RetiredMediaBlob.objects.filter(purged_at__isnull=True,purge_after__lte=at).values_list('id',flat=True)):
        with transaction.atomic():
            if not RetentionPolicy.objects.select_for_update().filter(purpose='media',enabled=True,minimum_seconds__isnull=False).exclude(review_reference='').exists():return count
            media_id=RetiredMediaBlob.objects.values_list('media_id',flat=True).get(pk=pk)
            CareMedia.objects.select_for_update().get(pk=media_id)
            blob=RetiredMediaBlob.objects.select_for_update(of=('self',)).select_related('media').get(pk=pk)
            if blob.purged_at or blob.media.legal_hold or (blob.media.retention_until and blob.media.retention_until>at):continue
            if not isinstance(blob.media.file.storage,FileSystemStorage):continue
            blob.media.file.storage.delete(blob.storage_name)
            blob.purged_at=at;blob.save(update_fields=['purged_at'])
            audit(None,'privacy.retired_blob_purged',blob);count+=1
    return count


@transaction.atomic
def apply_correction(actor,pk,expected_version,values):
    from families.services import update_profile
    case=PrivacyRequest.objects.select_for_update().get(pk=pk)
    if is_device(actor) or case.requester_id!=actor.pk or case.kind!='correction' or case.status!='approved' or not case.child_id:
        raise PermissionDenied('Approved child correction for this requester required.')
    require_guardian(actor,case.child.household_id)
    child=update_profile(actor,case.child_id,values,expected_version)
    case.status='fulfilled';case.save(update_fields=['status'])
    audit(actor,'privacy.correction_applied',case,care_version=child.current_version)
    return case
