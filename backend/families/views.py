import hashlib
import secrets
import wave
from django.utils import timezone
from django.db import transaction
from django.http import FileResponse
from rest_framework import mixins, viewsets, serializers
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from common.audit import audit
from .access import is_device, require_guardian, require_child_access, visible_children, active_grants
from .models import Household, Guardian, Child, Device, EmergencyContact, CareMedia
from .serializers import HouseholdSerializer, ChildSerializer, DeviceSerializer, ContactSerializer, MediaSerializer

class NoDeviceMixin:
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if is_device(request.user):
            raise PermissionDenied('Adult guardian account required.')

class HouseholdView(NoDeviceMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = HouseholdSerializer
    def get_queryset(self):
        from django.db.models import Q
        return Household.objects.filter(Q(guardians__user=self.request.user)|Q(children__in=visible_children(self.request.user))).distinct().order_by('created_at','id')
    @transaction.atomic
    def perform_create(self, serializer):
        household = serializer.save()
        Guardian.objects.create(household=household, user=self.request.user)
        audit(self.request.user, 'household.created', household)

    @action(detail=True,methods=['get'])
    def entitlement(self,request,pk=None):
        household=self.get_object();require_guardian(request.user,household.id)
        from django.utils import timezone
        from .models import Entitlement
        ledger=Entitlement.objects.filter(household=household).first()
        audit(request.user,'entitlement.read',household)
        return Response({'active_entitlement':bool(ledger and ledger.eligible(timezone.now())),
            'starts_at':ledger.starts_at if ledger else None,'ends_at':ledger.ends_at if ledger else None,
            'record_available':ledger is not None,'source':ledger.source if ledger else None,
            'accepted_incidents_continue':True,'ordinary_emergency_call_separate':True})

class ChildView(NoDeviceMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    serializer_class = ChildSerializer
    def get_queryset(self):
        return visible_children(self.request.user).order_by('created_at','id')
    @transaction.atomic
    def perform_create(self, serializer):
        Household.objects.select_for_update().get(pk=serializer.validated_data['household'].id)
        require_guardian(self.request.user, serializer.validated_data['household'].id)
        serializer.validated_data.pop('expected_version',None)
        child = serializer.save()
        from .services import lock_child, capture_version
        child = lock_child(child.id)
        capture_version(child,self.request.user)
        serializer.instance = child
        audit(self.request.user, 'child.created', child)
    def perform_update(self, serializer):
        from .services import update_profile
        values = dict(serializer.validated_data)
        household = values.pop('household',serializer.instance.household)
        if household != serializer.instance.household:
            raise ValidationError('Moving a child between households is unsupported.')
        expected = values.pop('expected_version',None)
        serializer.instance = update_profile(self.request.user,serializer.instance.id,values,expected)
    def retrieve(self, request, *args, **kwargs):
        child = self.get_object()
        audit(request.user, 'child.read', child)
        return Response(self.get_serializer(child).data)
    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        for child in self.paginate_queryset(self.get_queryset()):
            audit(request.user, 'child.read', child)
        return response

    @action(detail=True,methods=['get'])
    def versions(self,request,pk=None):
        child=self.get_object()
        audit(request.user,'care.versions_read',child)
        page=self.paginate_queryset(child.care_versions.order_by('-number'))
        return self.get_paginated_response([{'number':v.number,'created_at':v.created_at,'author':v.author_id,'payload':v.payload} for v in page])

    @action(detail=True,methods=['get'])
    def readiness(self,request,pk=None):
        child=self.get_object()
        from django.utils import timezone
        from django.db.models import Q
        from .models import Entitlement
        ledger=Entitlement.objects.filter(household=child.household).first()
        audit(request.user,'child.readiness_read',child)
        return Response({'care_version':child.current_version,
            'profile_fields_set':[key for key in ['communication','support_needs','calming_preferences'] if getattr(child,key).strip()],
            'contact_count':child.contacts.filter(active=True).count(),
            'linked_device_count':child.devices.filter(revoked_at__isnull=True).filter(Q(expires_at__isnull=True)|Q(expires_at__gt=timezone.now())).count(),
            'active_entitlement':bool(ledger and ledger.eligible(timezone.now())),
            'coverage':'not_evaluated','required_care_fields':'not_configured','guaranteed_service':False})

class ChildOwnedView(NoDeviceMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    model = None
    def get_queryset(self):
        return self.model.objects.filter(child__in=visible_children(self.request.user)).order_by('created_at','id')
    @transaction.atomic
    def perform_create(self, serializer):
        child = serializer.validated_data['child']
        from .services import lock_child, capture_version
        child = lock_child(child.id)
        require_child_access(self.request.user,child,'manage_profile')
        obj = serializer.save()
        if self.model == EmergencyContact: capture_version(child,self.request.user)
        audit(self.request.user, self.model.__name__.lower()+'.created', obj)

    def list(self,request,*args,**kwargs):
        response=super().list(request,*args,**kwargs)
        for obj in self.paginate_queryset(self.get_queryset()):
            audit(request.user,'family.resource_read',obj,model=obj._meta.label)
        return response
    def retrieve(self,request,*args,**kwargs):
        obj=self.get_object()
        audit(request.user,'family.resource_read',obj,model=obj._meta.label)
        return Response(self.get_serializer(obj).data)

class DeviceView(ChildOwnedView):
    def get_queryset(self):
        return Device.objects.filter(child__in=visible_children(self.request.user,'manage_devices')).order_by('created_at','id')
    model = Device
    serializer_class = DeviceSerializer
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        child = serializer.validated_data['child']
        from .services import lock_child
        child = lock_child(child.id)
        require_child_access(request.user,child,'manage_devices')
        token = secrets.token_urlsafe(32)
        from .lifecycle import credential_expiry
        device = serializer.save(token_digest=hashlib.sha256(token.encode()).hexdigest(),expires_at=credential_expiry())
        audit(request.user, 'device.linked', device)
        # Returned once. Only the hash is stored; do not log this response.
        return Response({**self.get_serializer(device).data, 'credential': token}, status=201)
    @action(detail=True,methods=['post'])
    def rotate(self,request,pk=None):
        obj=self.get_object()
        from .lifecycle import rotate_device
        obj,token=rotate_device(request.user,obj.id)
        return Response({**self.get_serializer(obj).data,'credential':token},status=201)
    @action(detail=True, methods=['post'])
    def revoke(self, request, pk=None):
        device = self.get_object()
        from incidents.services import revoke_device
        device = revoke_device(request.user, device.pk)
        return Response(self.get_serializer(device).data)

class ContactView(mixins.UpdateModelMixin, ChildOwnedView):
    model = EmergencyContact
    serializer_class = ContactSerializer
    @transaction.atomic
    def perform_update(self,serializer):
        from .services import lock_child,capture_version
        child=lock_child(serializer.instance.child_id)
        require_child_access(self.request.user,child,'manage_profile')
        if serializer.validated_data.get('child',child) != child:
            raise ValidationError('Cannot move a contact between children.')
        obj=serializer.save()
        capture_version(child,self.request.user)
        audit(self.request.user,'contact.updated',obj)

class MediaView(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    serializer_class = MediaSerializer
    def get_queryset(self):
        actor = self.request.user
        if is_device(actor):
            return CareMedia.objects.filter(child=actor.device.child, for_child=True,archived_at__isnull=True).order_by('created_at','id')
        from django.db.models import Q
        from operations.models import FacilityStaff
        facilities=FacilityStaff.objects.filter(user=actor,active=True,on_duty=True).exclude(review_reference='').values('facility_id')
        return CareMedia.objects.filter(archived_at__isnull=True).filter(
            Q(child__household__guardians__user=actor) |
            Q(child_id__in=active_grants(actor,'view_care').values('child_id')) |
            Q(for_responder=True,child__incident__placements__staff=actor,child__incident__placements__facility_id__in=facilities,child__incident__placements__state__in=['reserved','intake'],child__incident__state__in=['received','triage','active']) |
            Q(for_responder=True, child__incident__region__coordinator__user=actor, child__incident__state__in=['received','triage','active']) |
            Q(for_responder=True, child__incident__assignments__team__members=actor, child__incident__assignments__state__in=['accepted','en_route','arrived'], child__incident__state__in=['received','triage','active'])
        ).distinct().order_by('created_at','id')
    @transaction.atomic
    def perform_create(self, serializer):
        child = serializer.validated_data['child']
        require_child_access(self.request.user,child,'manage_media')
        media = serializer.save()
        audit(self.request.user, 'media.created', media)
    @transaction.atomic
    def perform_update(self, serializer):
        from .services import lock_child
        child=lock_child(serializer.instance.child_id)
        serializer.instance=CareMedia.objects.select_for_update().get(pk=serializer.instance.pk,archived_at__isnull=True)
        require_child_access(self.request.user,child,'manage_media')
        if serializer.validated_data.get('child', serializer.instance.child) != serializer.instance.child:
            raise ValidationError('Cannot move media between children.')
        media = serializer.save()
        audit(self.request.user, 'media.updated', media)
    def retrieve(self, request, *args, **kwargs):
        obj = self.get_object()
        audit(request.user, 'media.read', obj)
        return Response(self.get_serializer(obj).data)
    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        for obj in self.paginate_queryset(self.get_queryset()):
            audit(request.user, 'media.read', obj)
        return response
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def upload(self, request, pk=None):
        obj = self.get_object()
        from .services import lock_child
        child=lock_child(obj.child_id)
        obj=CareMedia.objects.select_for_update().get(pk=obj.id,archived_at__isnull=True)
        require_child_access(request.user,child,'manage_media')
        file = request.FILES.get('audio')
        if not file or file.size > 5 * 1024 * 1024:
            raise ValidationError('A WAV file of at most 5 MiB is required.')
        try:
            with wave.open(file, 'rb') as audio:
                if audio.getcomptype()!='NONE' or audio.getnchannels()>2 or audio.getnframes()/audio.getframerate()>180:
                    raise ValueError()
                expected=audio.getnframes()*audio.getnchannels()*audio.getsampwidth()
                if expected>5*1024*1024 or len(audio.readframes(audio.getnframes()+1))!=expected:
                    raise ValueError()
        except (wave.Error, EOFError, ValueError, ZeroDivisionError):
            raise ValidationError('Valid PCM WAV audio up to 180 seconds required.')
        file.seek(0)
        # Keep replaced blobs private until a reviewed retention policy permits purge.
        from .models import RetiredMediaBlob
        from common.models import RetentionPolicy
        from datetime import timedelta
        old_name=obj.file.name
        if old_name:
            policy=RetentionPolicy.objects.filter(purpose='media',enabled=True,minimum_seconds__isnull=False).exclude(review_reference='').first()
            RetiredMediaBlob.objects.create(media=obj,storage_name=old_name,purge_after=timezone.now()+timedelta(seconds=policy.minimum_seconds) if policy else None)
        obj.file.save(secrets.token_hex(16)+'.wav', file)
        audit(request.user, 'media.uploaded', obj)
        return Response(self.get_serializer(obj).data)
    @action(detail=True, methods=['get'])
    def audio(self, request, pk=None):
        obj = self.get_object()
        if not obj.file:
            from rest_framework.exceptions import NotFound
            raise NotFound()
        audit(request.user, 'media.audio_read', obj)
        response = FileResponse(obj.file.open('rb'), content_type='audio/wav')
        response['Cache-Control'] = 'private, no-store'
        return response
