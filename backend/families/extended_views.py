from drf_spectacular.utils import extend_schema
from django.db import transaction
from django.db.models import Q
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import mixins, viewsets, serializers
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from common.audit import audit
from .views import NoDeviceMixin
from .access import visible_children,require_guardian,require_child_access
from .models import (CaregiverGrant,CaregiverInvitation,SavedPlace,AuthorityRecord,Child)
from .serializers import GrantSerializer,InvitationSerializer,SavedPlaceSerializer
from . import services

class AuditedReadMixin:
    def list(self,request,*args,**kwargs):
        response=super().list(request,*args,**kwargs)
        for obj in self.paginate_queryset(self.get_queryset()):
            audit(request.user,'family.resource_read',obj,model=obj._meta.label)
        return response
    def retrieve(self,request,*args,**kwargs):
        obj=self.get_object()
        audit(request.user,'family.resource_read',obj,model=obj._meta.label)
        return Response(self.get_serializer(obj).data)

class GrantView(AuditedReadMixin,NoDeviceMixin,mixins.ListModelMixin,mixins.RetrieveModelMixin,viewsets.GenericViewSet):
    serializer_class=GrantSerializer
    def get_queryset(self):
        return CaregiverGrant.objects.filter(Q(user=self.request.user)|Q(child__household__guardians__user=self.request.user)).distinct().order_by('created_at','id')
    @action(detail=True,methods=['post'])
    def revoke(self,request,pk=None):
        grant=self.get_object()
        obj=services.revoke_grant(request.user,grant.id)
        return Response(self.get_serializer(obj).data)

class InvitationViewConsumeInput(serializers.Serializer):
    token = serializers.CharField(min_length=20, max_length=200)
    accept = serializers.BooleanField(default=True)

class InvitationView(AuditedReadMixin,NoDeviceMixin,mixins.ListModelMixin,mixins.RetrieveModelMixin,mixins.CreateModelMixin,viewsets.GenericViewSet):
    serializer_class=InvitationSerializer
    def get_queryset(self):
        return CaregiverInvitation.objects.filter(Q(recipient=self.request.user)|Q(child__household__guardians__user=self.request.user)).distinct().order_by('created_at','id')
    def create(self,request,*args,**kwargs):
        serializer=self.get_serializer(data=request.data);serializer.is_valid(raise_exception=True)
        d=serializer.validated_data
        invite,token=services.invite_caregiver(request.user,d['child'].id,d['recipient'],d['relationship'],d['permissions'])
        return Response({**self.get_serializer(invite).data,'invitation_token':token,'delivery':'manual_sandbox_only'},status=201)
    @extend_schema(request=InvitationViewConsumeInput, methods=["POST"])
    @action(detail=False,methods=['post'])
    def consume(self,request):
        Input = InvitationViewConsumeInput
        serializer=Input(data=request.data);serializer.is_valid(raise_exception=True)
        invite=services.accept_invitation(request.user,**serializer.validated_data)
        return Response(self.get_serializer(invite).data)
    @action(detail=True,methods=['post'])
    @transaction.atomic
    def revoke(self,request,pk=None):
        invite=self.get_object();child=services.lock_child(invite.child_id)
        require_guardian(request.user,child.household_id)
        invite=CaregiverInvitation.objects.select_for_update().get(pk=invite.id)
        if invite.status=='accepted':
            CaregiverGrant.objects.filter(child=child,user=invite.recipient).update(revoked_at=timezone.now())
        invite.status='revoked';invite.save(update_fields=['status'])
        audit(request.user,'caregiver.invitation_revoked',invite)
        return Response(self.get_serializer(invite).data)

class PlaceView(AuditedReadMixin,NoDeviceMixin,mixins.ListModelMixin,mixins.RetrieveModelMixin,mixins.CreateModelMixin,mixins.UpdateModelMixin,viewsets.GenericViewSet):
    serializer_class=SavedPlaceSerializer
    def get_queryset(self):
        return SavedPlace.objects.filter(child__in=visible_children(self.request.user)).order_by('created_at','id')
    def perform_create(self,serializer):
        d=dict(serializer.validated_data);child=d.pop('child')
        serializer.instance=services.save_place(self.request.user,child.id,d)
    def perform_update(self,serializer):
        d=dict(serializer.validated_data);child=d.pop('child',serializer.instance.child)
        if child != serializer.instance.child:raise ValidationError('Cannot move a place between children.')
        serializer.instance=services.save_place(self.request.user,child.id,d,serializer.instance.id)

class AuthoritySerializer(serializers.ModelSerializer):
    class Meta:
        model=AuthorityRecord
        fields=['id','child','subject','purpose','status','evidence_reference','verification_reference','verified_by','verified_at','valid_until']
        read_only_fields=['id','status','verification_reference','verified_by','verified_at']
    def validate_valid_until(self,value):
        if value and value<=timezone.now():raise serializers.ValidationError('Validity must be in the future.')
        return value

class AuthorityViewReviewInput(serializers.Serializer):
    incident = serializers.UUIDField()
    status = serializers.ChoiceField(choices=['verified', 'revoked'])
    verification_reference = serializers.CharField(max_length=200)

class AuthorityView(AuditedReadMixin,NoDeviceMixin,mixins.ListModelMixin,mixins.RetrieveModelMixin,mixins.CreateModelMixin,viewsets.GenericViewSet):
    serializer_class=AuthoritySerializer
    def get_queryset(self):
        return AuthorityRecord.objects.filter(
            Q(child__household__guardians__user=self.request.user)|Q(subject=self.request.user)|
            Q(child__incident__region__coordinator__user=self.request.user,child__incident__state__in=['received','triage','active'])
        ).distinct().order_by('created_at','id')
    @transaction.atomic
    def perform_create(self,serializer):
        child=services.lock_child(serializer.validated_data['child'].id)
        require_guardian(self.request.user,child.household_id)
        obj=serializer.save()
        audit(self.request.user,'authority.submitted',obj)
    @extend_schema(request=AuthorityViewReviewInput, methods=["POST"])
    @action(detail=True,methods=['post'])
    @transaction.atomic
    def review(self,request,pk=None):
        from incidents.services import lock_incident
        from incidents.access import require_coordinator
        Input = AuthorityViewReviewInput
        serializer=Input(data=request.data);serializer.is_valid(raise_exception=True)
        d=serializer.validated_data;incident=lock_incident(d['incident']);require_coordinator(request.user,incident)
        obj=AuthorityRecord.objects.select_for_update().get(pk=pk,child_id=incident.child_id)
        if incident.state not in ['received','triage','active']:raise ValidationError('Open regional incident required.')
        if d['status']=='verified' and (not obj.valid_until or obj.valid_until<=timezone.now()):
            raise ValidationError('A future validity limit is required for recorded verification.')
        obj.status=d['status'];obj.verification_reference=d['verification_reference']
        obj.verified_by=request.user;obj.verified_at=timezone.now();obj.save()
        audit(request.user,'authority.review_recorded',obj,status=obj.status)
        return Response(self.get_serializer(obj).data)
