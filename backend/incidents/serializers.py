from rest_framework import serializers
from .models import Incident
from .services import continuation_status, public_status

class LocationSerializer(serializers.Serializer):
    latitude = serializers.FloatField(min_value=-90, max_value=90)
    longitude = serializers.FloatField(min_value=-180, max_value=180)
    accuracy_meters = serializers.FloatField(min_value=0)
    captured_at = serializers.DateTimeField()
    def validate(self, attrs):
        import math
        if not all(math.isfinite(attrs[key]) for key in ['latitude', 'longitude', 'accuracy_meters']):
            raise serializers.ValidationError('Finite location values required.')
        return attrs

class HelpSerializer(serializers.Serializer):
    child = serializers.UUIDField()
    request_id = serializers.UUIDField()
    location = LocationSerializer(required=False, default=dict)

class IncidentSerializer(serializers.ModelSerializer):
    public_status = serializers.SerializerMethodField()
    def get_public_status(self, obj):
        return public_status(obj)
    continuation = serializers.SerializerMethodField()
    crew_state = serializers.SerializerMethodField()
    placement_state = serializers.SerializerMethodField()
    notification_status = serializers.SerializerMethodField()
    def get_crew_state(self, obj):
        assignment = obj.assignments.order_by('-created_at').first()
        return assignment.state if assignment else 'unassigned'
    def get_placement_state(self, obj):
        placement = obj.placements.order_by('-created_at').first()
        return placement.state if placement else 'not_requested'
    def get_notification_status(self, obj):
        return [{'audience': n.audience, 'delivery': n.state, 'acknowledged_at': n.acknowledged_at} for n in obj.notifications.all()]
    ems_state = serializers.CharField(source='ems.state', read_only=True)
    def get_continuation(self, obj):
        return continuation_status(obj)
    class Meta:
        model = Incident
        fields = ['id','child','region','coordinator_owner','state','accepted_at','location','location_quality','saved_address_fallback','review_required','cancellation_requested','continuation','ems_state','crew_state','placement_state','notification_status','public_status']
        read_only_fields = fields

class LifecycleSerializer(serializers.Serializer):
    target = serializers.ChoiceField(choices=['triage','active','resolved','cancelled'])
    outcome = serializers.CharField(required=False, default='', allow_blank=True, max_length=2000)
    reconciled = serializers.BooleanField(required=False, default=False)

class OfferSerializer(serializers.Serializer):
    team = serializers.UUIDField()
    suitability_confirmed = serializers.BooleanField()

class AssignmentTransitionSerializer(serializers.Serializer):
    assignment = serializers.UUIDField()
    reason = serializers.CharField(required=False, default='', allow_blank=True, max_length=500)
    target = serializers.ChoiceField(choices=['accepted','declined','en_route','arrived','complete'])

class EMSSerializer(serializers.Serializer):
    state = serializers.ChoiceField(choices=['unknown','contact_confirmed','dispatch_confirmed','arrived','no_dispatch','closed'])
    evidence = serializers.CharField(max_length=2000)

class ReserveSerializer(serializers.Serializer):
    facility = serializers.UUIDField()
    authority_reference = serializers.CharField(max_length=200)
    suitability_confirmed = serializers.BooleanField()

class PlacementTransitionSerializer(serializers.Serializer):
    placement = serializers.UUIDField()
    target = serializers.ChoiceField(choices=['intake','released','cancelled'])
    handover_reference = serializers.CharField(max_length=200)
