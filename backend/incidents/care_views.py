from drf_spectacular.utils import extend_schema
from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import mixins,viewsets,serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from common.audit import audit
from families.access import is_device
from .models import Placement
from . import care

class PlacementViewAssignStaffInput(serializers.Serializer):
    recipient = serializers.PrimaryKeyRelatedField(queryset=get_user_model().objects.filter(is_active=True))
    reference = serializers.CharField(max_length=200)

class PlacementViewAcceptHandoverInput(serializers.Serializer):
    handover = serializers.UUIDField()

class PlacementViewEventsInput(serializers.Serializer):
    event_id = serializers.UUIDField()
    kind = serializers.ChoiceField(choices=['support', 'observation', 'handover_note'])
    note = serializers.CharField(max_length=2000)

class PlacementHandoverDecisionInput(serializers.Serializer):
    handover_id=serializers.UUIDField()
    target=serializers.ChoiceField(choices=['declined','cancelled'])
    reference=serializers.CharField(max_length=200)

class PlacementView(mixins.ListModelMixin,mixins.RetrieveModelMixin,viewsets.GenericViewSet):
    def get_queryset(self):
        actor=self.request.user
        if is_device(actor):return Placement.objects.none()
        from operations.models import FacilityStaff
        staff_facilities=FacilityStaff.objects.filter(user=actor,active=True,on_duty=True).exclude(review_reference='').values('facility_id')
        return Placement.objects.filter(incident__state__in=['received','triage','active']).filter(
            Q(incident__region__coordinator__user=actor)|
            Q(staff=actor,facility_id__in=staff_facilities,state__in=['reserved','intake'])).distinct().order_by('created_at','id')
    def payload(self,obj):
        snapshot=obj.incident.care_version.payload if obj.incident.care_version_id else {}
        care_summary={key:snapshot.get(key,[] if key=='contacts' else '') for key in ['name','communication','support_needs','calming_preferences','contacts']}
        return {'id':obj.id,'incident':obj.incident_id,'facility':obj.facility_id,'care_place':obj.care_place_id,
            'care':care_summary,'state':obj.state,'reserved_until':obj.reserved_until,'intake_at':obj.intake_at,'released_at':obj.released_at,'current_staff':obj.current_staff_id,
            'staff':list(obj.staff.values_list('id',flat=True)),'authority':obj.authority_id,
            'transport_reference':obj.transport_reference,'intake_reference':obj.intake_reference,'belongings':obj.belongings}
    def list(self,request,*args,**kwargs):
        page=self.paginate_queryset(self.get_queryset())
        for item in page:audit(request.user,'care.placements_read',item)
        return self.get_paginated_response([self.payload(item) for item in page])
    def retrieve(self,request,*args,**kwargs):
        obj=self.get_object();audit(request.user,'care.placement_read',obj)
        return Response(self.payload(obj))
    @extend_schema(request=PlacementViewAssignStaffInput, methods=["POST"])
    @action(detail=True,methods=['post'],url_path='assign-staff')
    def assign_staff(self,request,pk=None):
        obj=self.get_object()
        Input = PlacementViewAssignStaffInput
        s=Input(data=request.data);s.is_valid(raise_exception=True)
        handover=care.assign_staff(request.user,obj.id,**s.validated_data)
        return Response({'handover':handover.id,'status':handover.status},status=201)
    @action(detail=True,methods=['get'])
    def handovers(self,request,pk=None):
        obj=self.get_object();care.require_staff_or_coordinator(request.user,obj)
        audit(request.user,'care.handovers_read',obj)
        page=self.paginate_queryset(obj.handovers.order_by('created_at','id'))
        return self.get_paginated_response([{'id':item.id,'kind':item.kind,'source':item.source_id,'recipient':item.recipient_id,
            'status':item.status,'reference':item.reference,'accepted_at':item.accepted_at} for item in page])
    @extend_schema(request=PlacementViewAcceptHandoverInput, methods=["POST"])
    @action(detail=True,methods=['post'],url_path='accept-handover')
    def accept_handover(self,request,pk=None):
        obj=self.get_object()
        Input = PlacementViewAcceptHandoverInput
        s=Input(data=request.data);s.is_valid(raise_exception=True)
        handover=care.accept_staff_handover(request.user,obj.id,s.validated_data['handover'])
        return Response({'id':handover.id,'status':handover.status})
    @extend_schema(request=PlacementViewEventsInput, methods=["POST"])
    @action(detail=True,methods=['get','post'])
    def events(self,request,pk=None):
        obj=self.get_object();care.require_staff_or_coordinator(request.user,obj)
        if request.method=='POST':
            Input = PlacementViewEventsInput
            s=Input(data=request.data);s.is_valid(raise_exception=True)
            item=care.record_care_event(request.user,obj.id,**s.validated_data)
            return Response({'id':item.id},status=201)
        audit(request.user,'care.events_read',obj)
        page=self.paginate_queryset(obj.care_events.order_by('created_at','id'))
        return self.get_paginated_response([{'id':item.id,'event_id':item.event_id,'author':item.author_id,'kind':item.kind,
            'note':item.note,'created_at':item.created_at} for item in page])
    @action(detail=True,methods=['post'])
    def transition(self,request,pk=None):
        obj=self.get_object()
        from .serializers import PlacementTransitionSerializer
        s=PlacementTransitionSerializer(data={**request.data,'placement':str(obj.id)});s.is_valid(raise_exception=True)
        d=s.validated_data
        obj=care.transition_care(request.user,obj.incident_id,obj.id,d['target'],d['handover_reference'],d.get('recipient'),d.get('authority'),
            d['transport_reference'],d['intake_reference'],d['belongings'])
        return Response(self.payload(obj))

    @extend_schema(request=PlacementHandoverDecisionInput)
    @action(detail=True,methods=['post'],url_path='handover-decision')
    def handover_decision(self,request,pk=None):
        obj=self.get_object()
        s=PlacementHandoverDecisionInput(data=request.data);s.is_valid(raise_exception=True)
        item=care.end_staff_handover(request.user,obj.id,**s.validated_data)
        return Response({'id':item.id,'status':item.status})
