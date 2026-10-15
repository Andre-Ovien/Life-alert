from drf_spectacular.utils import extend_schema
from django.db import transaction
from rest_framework import serializers,mixins,viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied,ValidationError
from common.audit import audit
from families.access import is_device
from families.views import NoDeviceMixin
from .models import PrivacyRequest,RetentionPolicy
from . import privacy

class PrivacyRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model=PrivacyRequest
        fields=['id','request_id','kind','child','media','details','status','review_reference','purge_after','created_at']
        read_only_fields=['id','status','review_reference','purge_after','created_at']

class PrivacyRequestViewReviewInput(serializers.Serializer):
    target = serializers.ChoiceField(choices=['approved', 'hold', 'denied'])
    reference = serializers.CharField(max_length=200)

class PrivacyRequestViewCorrectInput(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=0)
    values = serializers.DictField(child=serializers.CharField(max_length=10000, allow_blank=True))

class PrivacyRequestViewMediaHoldInput(serializers.Serializer):
    legal_hold = serializers.BooleanField()
    retention_until = serializers.DateTimeField(required=False, allow_null=True)
    reference = serializers.CharField(max_length=200)

class PrivacyRequestView(NoDeviceMixin,mixins.ListModelMixin,mixins.RetrieveModelMixin,mixins.CreateModelMixin,viewsets.GenericViewSet):
    serializer_class=PrivacyRequestSerializer
    def get_queryset(self):
        query=PrivacyRequest.objects.all() if self.request.user.has_perm('common.review_privacyrequest') else PrivacyRequest.objects.filter(requester=self.request.user)
        return query.order_by('created_at','id')
    def create(self,request,*args,**kwargs):
        s=self.get_serializer(data=request.data);s.is_valid(raise_exception=True);d=dict(s.validated_data)
        child=d.pop('child',None);media=d.pop('media',None)
        obj=privacy.submit_request(request.user,child_id=child.id if child else None,media_id=media.id if media else None,**d)
        return Response(self.get_serializer(obj).data,status=201)
    def retrieve(self,request,*args,**kwargs):
        obj=self.get_object();audit(request.user,'privacy.request_read',obj)
        return Response(self.get_serializer(obj).data)
    def list(self,request,*args,**kwargs):
        response=super().list(request,*args,**kwargs)
        for obj in self.paginate_queryset(self.get_queryset()):audit(request.user,'privacy.request_read',obj)
        return response
    @extend_schema(request=PrivacyRequestViewReviewInput, methods=["POST"])
    @action(detail=True,methods=['post'])
    def review(self,request,pk=None):
        obj=self.get_object()
        Input = PrivacyRequestViewReviewInput
        s=Input(data=request.data);s.is_valid(raise_exception=True)
        obj=privacy.review_request(request.user,obj.id,**s.validated_data)
        return Response(self.get_serializer(obj).data)
    @action(detail=True,methods=['get'])
    def export(self,request,pk=None):
        obj=self.get_object();payload=privacy.prepare_export(request.user,obj.id)
        response=Response(payload)
        response['Content-Disposition']='attachment; filename="reviewed-application-records.json"'
        return response
    @extend_schema(request=PrivacyRequestViewCorrectInput, methods=["POST"])
    @action(detail=True,methods=['post'])
    def correct(self,request,pk=None):
        obj=self.get_object()
        Input = PrivacyRequestViewCorrectInput
        s=Input(data=request.data);s.is_valid(raise_exception=True)
        obj=privacy.apply_correction(request.user,obj.id,**s.validated_data)
        return Response(self.get_serializer(obj).data)
    @extend_schema(request=PrivacyRequestViewMediaHoldInput, methods=["POST"])
    @action(detail=True,methods=['post'],url_path='media-hold')
    @transaction.atomic
    def media_hold(self,request,pk=None):
        obj=self.get_object();privacy.require_privacy_reviewer(request.user)
        if not obj.media_id:raise ValidationError('Media-scoped request required.')
        Input = PrivacyRequestViewMediaHoldInput
        s=Input(data=request.data);s.is_valid(raise_exception=True)
        from families.models import CareMedia
        media=CareMedia.objects.select_for_update().get(pk=obj.media_id)
        media.legal_hold=s.validated_data['legal_hold']
        if 'retention_until' in s.validated_data:media.retention_until=s.validated_data['retention_until']
        media.save(update_fields=['legal_hold','retention_until'])
        # Preserve the human review reference as protected case data, not logs.
        obj.review_reference=s.validated_data['reference'];obj.save(update_fields=['review_reference'])
        from .models import PrivacyDecision
        PrivacyDecision.objects.create(request=obj,actor=request.user,decision='hold' if media.legal_hold else 'hold_lifted',reference=s.validated_data['reference'])
        audit(request.user,'privacy.media_hold_recorded',obj,legal_hold=media.legal_hold)
        return Response({'legal_hold':media.legal_hold,'retention_until':media.retention_until})

class RetentionPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model=RetentionPolicy
        fields=['id','purpose','enabled','minimum_seconds','review_reference']
        read_only_fields=['id']
    def validate(self,data):
        obj=self.instance
        if data.get('purpose',getattr(obj,'purpose','media'))!='media':raise serializers.ValidationError('Only the media retention contract is implemented.')
        if data.get('enabled',getattr(obj,'enabled',False)) and (data.get('minimum_seconds',getattr(obj,'minimum_seconds',None)) is None or not data.get('review_reference',getattr(obj,'review_reference',''))):
            raise serializers.ValidationError('Explicit retention interval and reviewed policy reference required.')
        return data

from operations.views import ConfigView
class RetentionPolicyView(ConfigView):
    queryset=RetentionPolicy.objects.all().order_by('created_at','id')
    serializer_class=RetentionPolicySerializer
