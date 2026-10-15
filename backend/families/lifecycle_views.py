from drf_spectacular.utils import extend_schema
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.throttling import ScopedRateThrottle
from rest_framework import mixins,viewsets,serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from common.audit import audit
from operations.views import ConfigurationAdmin
from .access import visible_children
from .views import NoDeviceMixin
from .models import DeviceLinkChallenge
from . import lifecycle

class PairingSerializer(serializers.ModelSerializer):
    class Meta:
        model=DeviceLinkChallenge
        fields=['id','child','label','expires_at','consumed_at','revoked_at']
        read_only_fields=['id','expires_at','consumed_at','revoked_at']

class PairingView(NoDeviceMixin,mixins.ListModelMixin,mixins.RetrieveModelMixin,mixins.CreateModelMixin,viewsets.GenericViewSet):
    serializer_class=PairingSerializer
    def get_queryset(self):
        return DeviceLinkChallenge.objects.filter(child__in=visible_children(self.request.user,'manage_devices')).order_by('created_at','id')
    def create(self,request,*args,**kwargs):
        s=self.get_serializer(data=request.data);s.is_valid(raise_exception=True)
        obj,raw=lifecycle.start_pairing(request.user,s.validated_data['child'].id,s.validated_data['label'])
        return Response({**self.get_serializer(obj).data,'pairing_token':raw},status=201)
    @action(detail=True,methods=['post'])
    def revoke(self,request,pk=None):
        obj=self.get_object();obj=lifecycle.revoke_pairing(request.user,obj.id)
        return Response(self.get_serializer(obj).data)

class PairingConsumeViewPostInput(serializers.Serializer):
    token = serializers.CharField(min_length=20, max_length=200)

class PairingConsumeView(APIView):
    permission_classes=[AllowAny];authentication_classes=[]
    throttle_classes=[ScopedRateThrottle];throttle_scope='pairing'
    @extend_schema(request=PairingConsumeViewPostInput, methods=["POST"])
    def post(self,request):
        Input = PairingConsumeViewPostInput
        s=Input(data=request.data);s.is_valid(raise_exception=True)
        device,token=lifecycle.consume_pairing(s.validated_data['token'])
        return Response({'id':device.id,'child':device.child_id,'credential':token,'expires_at':device.expires_at},status=201)

class SandboxBillingViewCreateInput(serializers.Serializer):
    household = serializers.UUIDField()
    event_id = serializers.CharField(max_length=120)
    revision = serializers.IntegerField(min_value=1)
    active = serializers.BooleanField()
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()

class SandboxBillingView(viewsets.GenericViewSet):
    permission_classes=[ConfigurationAdmin]
    @extend_schema(request=SandboxBillingViewCreateInput, methods=["POST"])
    def create(self,request):
        Input = SandboxBillingViewCreateInput
        s=Input(data=request.data);s.is_valid(raise_exception=True);d=dict(s.validated_data)
        event=lifecycle.apply_sandbox_billing_event(request.user,d.pop('household'),**d)
        return Response({'id':event.id,'status':event.status,'simulation':True})
