from django.shortcuts import get_object_or_404
from rest_framework import mixins, viewsets, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from common.audit import audit
from families.access import is_device
from .access import visible_incidents
from .models import Assignment, Placement
from .serializers import (HelpSerializer, IncidentSerializer, LifecycleSerializer, OfferSerializer, AssignmentTransitionSerializer, EMSSerializer, ReserveSerializer, PlacementTransitionSerializer)
from . import services

class IncidentView(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = IncidentSerializer
    def get_queryset(self):
        return visible_incidents(self.request.user).select_related('child','region','ems').order_by('-accepted_at')
    def payload(self, incident):
        actor = self.request.user
        if is_device(actor):
            return {'id': str(incident.id), 'state': incident.state, 'review_required': incident.review_required,
                    'cancellation_requested': incident.cancellation_requested, 'receipt': 'server_received',
                    'emergency_call_separate': True, 'public_status': services.public_status(incident)}
        return self.get_serializer(incident).data
    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())
        for obj in page:
            audit(request.user, 'incident.read', obj)
        return self.get_paginated_response([self.payload(obj) for obj in page])
    def retrieve(self, request, *args, **kwargs):
        incident = self.get_object()
        audit(request.user, 'incident.read', incident)
        return Response(self.payload(incident))
    @action(detail=False, methods=['post'])
    def help(self, request):
        serializer = HelpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        incident, result = services.create_incident(request.user, data['child'], data['request_id'], data['location'])
        payload = self.payload(incident)
        if result == 'followup_requires_review':
            payload['public_status'] = {'code': 'followup_requires_review', 'message': 'New information received for coordinator review. A separate response is not confirmed.'}
        return Response({'incident': payload, 'result': result,
                         'separate_event_review_required': result == 'followup_requires_review'}, status=201 if result == 'accepted' else 200)
    @action(detail=True, methods=['post'])
    def transition(self, request, pk=None):
        self.get_object()
        serializer = LifecycleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj = services.transition(request.user, pk, **serializer.validated_data)
        return Response(self.payload(obj))
    @action(detail=True, methods=['post'], url_path='request-cancellation')
    def request_cancellation(self, request, pk=None):
        self.get_object()
        return Response(self.payload(services.request_cancellation(request.user, pk)))
    @action(detail=True, methods=['post'], url_path='acknowledge-notification')
    def acknowledge_notification(self, request, pk=None):
        self.get_object()
        class Input(serializers.Serializer):
            audience = serializers.ChoiceField(choices=['guardian','coordinator'])
        serializer = Input(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj = services.acknowledge_notification(request.user, pk, serializer.validated_data['audience'])
        return Response({'audience': obj.audience, 'delivery': obj.state, 'acknowledged_at': obj.acknowledged_at})
    @action(detail=True, methods=['get'])
    def followups(self, request, pk=None):
        incident = self.get_object()
        from .access import require_coordinator
        require_coordinator(request.user, incident)
        audit(request.user, 'incident.followups_read', incident)
        return Response({'results': list(incident.helprequest_set.order_by('created_at').values('id','key','location','created_at')[:100])})
    @action(detail=True, methods=['post'], url_path='claim-ownership')
    def claim(self, request, pk=None):
        self.get_object()
        class Input(serializers.Serializer):
            takeover_reason = serializers.CharField(required=False, default='', allow_blank=True, max_length=500)
        serializer = Input(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(self.payload(services.claim_ownership(request.user, pk, **serializer.validated_data)))
    @action(detail=True, methods=['get','post'], url_path='progress')
    def progress(self, request, pk=None):
        incident = self.get_object()
        from .access import require_coordinator
        require_coordinator(request.user, incident)
        if request.method == 'GET':
            audit(request.user, 'incident.progress_read', incident)
            return Response({'results': list(incident.progress_notes.order_by('created_at').values('id','author','created_at','action_taken','next_steps')[:100])})
        class Input(serializers.Serializer):
            action_taken = serializers.CharField(max_length=2000)
            next_steps = serializers.CharField(max_length=2000)
            review_completed = serializers.BooleanField(required=False, default=False)
        serializer = Input(data=request.data)
        serializer.is_valid(raise_exception=True)
        note = services.record_progress(request.user, pk, **serializer.validated_data)
        return Response({'id': note.id}, status=201)
    @action(detail=True, methods=['post'], url_path='offer-team')
    def offer_team(self, request, pk=None):
        self.get_object()
        serializer = OfferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        obj = services.offer_team(request.user, pk, data['team'], data['suitability_confirmed'])
        return Response({'id': obj.id, 'state': obj.state, 'deadline': obj.deadline}, status=201)
    @action(detail=True, methods=['get'])
    def care(self, request, pk=None):
        incident = self.get_object()
        from rest_framework.exceptions import PermissionDenied
        from families.access import guardian
        from .access import coordinator, responder
        if is_device(request.user) or not (guardian(request.user, incident.child.household_id) or coordinator(request.user, incident) or responder(request.user, incident)):
            raise PermissionDenied()
        child = incident.child
        audit(request.user, 'incident.care_read', incident)
        return Response({'name': child.name, 'communication': child.communication, 'support_needs': child.support_needs,
                         'calming_preferences': child.calming_preferences})
    @action(detail=True, methods=['post'], url_path='ems-evidence')
    def ems_evidence(self, request, pk=None):
        self.get_object()
        serializer = EMSSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj = services.record_ems(request.user, pk, **serializer.validated_data)
        return Response({'state': obj.state})
    @action(detail=True, methods=['post'], url_path='reserve-placement')
    def reserve(self, request, pk=None):
        self.get_object()
        serializer = ReserveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        obj = services.reserve_placement(request.user, pk, d['facility'], d['authority_reference'], d['suitability_confirmed'])
        return Response({'id': obj.id, 'state': obj.state}, status=201)
    @action(detail=True, methods=['post'], url_path='placement-transition')
    def placement_transition(self, request, pk=None):
        incident = self.get_object()
        serializer = PlacementTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        get_object_or_404(Placement, pk=d['placement'], incident=incident)
        obj = services.placement_transition(request.user, pk, d['placement'], d['target'], d['handover_reference'])
        return Response({'id': obj.id, 'state': obj.state})

class MyOffersView(viewsets.GenericViewSet):
    """Before acceptance, crew sees offer IDs only, not the child's identity or care."""
    def list(self, request):
        if is_device(request.user):
            return Response({'results': []})
        offers = Assignment.objects.filter(team__members=request.user, state__in=['offered','accepted','en_route','arrived']).order_by('created_at')
        return Response({'results': [{'id': x.id, 'incident': x.incident_id, 'state': x.state, 'deadline': x.deadline} for x in offers[:50]]})
    @action(detail=True, methods=['post'])
    def transition(self, request, pk=None):
        from rest_framework.exceptions import PermissionDenied
        if is_device(request.user):
            raise PermissionDenied()
        assignment = get_object_or_404(Assignment, pk=pk, team__members=request.user)
        serializer = AssignmentTransitionSerializer(data={**request.data, 'assignment': str(pk)})
        serializer.is_valid(raise_exception=True)
        obj = services.assignment_transition(request.user, assignment.incident_id, pk, serializer.validated_data['target'], serializer.validated_data['reason'])
        return Response({'id': obj.id, 'state': obj.state})
