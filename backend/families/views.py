import hashlib
import secrets
import wave
from django.db import transaction
from django.http import FileResponse
from rest_framework import mixins, viewsets, serializers
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from common.audit import audit
from .access import is_device, require_guardian
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
        return Household.objects.filter(guardians__user=self.request.user).order_by('created_at','id')
    @transaction.atomic
    def perform_create(self, serializer):
        household = serializer.save()
        Guardian.objects.create(household=household, user=self.request.user)
        audit(self.request.user, 'household.created', household)

class ChildView(NoDeviceMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    serializer_class = ChildSerializer
    def get_queryset(self):
        return Child.objects.filter(household__guardians__user=self.request.user).order_by('created_at','id')
    @transaction.atomic
    def perform_create(self, serializer):
        require_guardian(self.request.user, serializer.validated_data['household'].id)
        child = serializer.save()
        audit(self.request.user, 'child.created', child)
    @transaction.atomic
    def perform_update(self, serializer):
        if serializer.validated_data.get('household', serializer.instance.household) != serializer.instance.household:
            raise ValidationError('Moving a child between households is unsupported.')
        child = serializer.save()
        audit(self.request.user, 'child.updated', child)
    def retrieve(self, request, *args, **kwargs):
        child = self.get_object()
        audit(request.user, 'child.read', child)
        return Response(self.get_serializer(child).data)
    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        for child in self.paginate_queryset(self.get_queryset()):
            audit(request.user, 'child.read', child)
        return response

class ChildOwnedView(NoDeviceMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    model = None
    def get_queryset(self):
        return self.model.objects.filter(child__household__guardians__user=self.request.user).order_by('created_at','id')
    @transaction.atomic
    def perform_create(self, serializer):
        child = serializer.validated_data['child']
        require_guardian(self.request.user, child.household_id)
        obj = serializer.save()
        audit(self.request.user, self.model.__name__.lower()+'.created', obj)

class DeviceView(ChildOwnedView):
    model = Device
    serializer_class = DeviceSerializer
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        child = serializer.validated_data['child']
        require_guardian(request.user, child.household_id)
        token = secrets.token_urlsafe(32)
        device = serializer.save(token_digest=hashlib.sha256(token.encode()).hexdigest())
        audit(request.user, 'device.linked', device)
        # Returned once. Only the hash is stored; do not log this response.
        return Response({**self.get_serializer(device).data, 'credential': token}, status=201)
    @action(detail=True, methods=['post'])
    def revoke(self, request, pk=None):
        device = self.get_object()
        from incidents.services import revoke_device
        device = revoke_device(request.user, device.pk)
        return Response(self.get_serializer(device).data)

class ContactView(ChildOwnedView):
    model = EmergencyContact
    serializer_class = ContactSerializer

class MediaView(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    serializer_class = MediaSerializer
    def get_queryset(self):
        actor = self.request.user
        if is_device(actor):
            return CareMedia.objects.filter(child=actor.device.child, for_child=True).order_by('created_at','id')
        from django.db.models import Q
        return CareMedia.objects.filter(
            Q(child__household__guardians__user=actor) |
            Q(for_responder=True, child__incident__region__coordinator__user=actor, child__incident__state__in=['received','triage','active']) |
            Q(for_responder=True, child__incident__assignments__team__members=actor, child__incident__assignments__state__in=['accepted','en_route','arrived'], child__incident__state__in=['received','triage','active'])
        ).distinct().order_by('created_at','id')
    @transaction.atomic
    def perform_create(self, serializer):
        child = serializer.validated_data['child']
        require_guardian(self.request.user, child.household_id)
        media = serializer.save()
        audit(self.request.user, 'media.created', media)
    @transaction.atomic
    def perform_update(self, serializer):
        require_guardian(self.request.user, serializer.instance.child.household_id)
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
    def upload(self, request, pk=None):
        obj = self.get_object()
        require_guardian(request.user, obj.child.household_id)
        file = request.FILES.get('audio')
        if not file or file.size > 5 * 1024 * 1024:
            raise ValidationError('A WAV file of at most 5 MiB is required.')
        try:
            with wave.open(file, 'rb') as audio:
                if audio.getnchannels() > 2 or audio.getnframes()/audio.getframerate() > 180:
                    raise ValueError()
        except (wave.Error, EOFError, ValueError, ZeroDivisionError):
            raise ValidationError('Valid PCM WAV audio up to 180 seconds required.')
        file.seek(0)
        # Store opaque filenames only. Old blobs need reviewed retention cleanup.
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
