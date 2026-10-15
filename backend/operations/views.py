"""Configuration-only administrative boundary, separate from child-data access."""
from django.db import transaction
from rest_framework import serializers, mixins, viewsets
from rest_framework.permissions import BasePermission
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.utils import timezone
from common.audit import audit
from families.access import is_device
from families.models import Entitlement, Household
from .models import Region, Team, Facility, Coordinator

class ConfigurationAdmin(BasePermission):
    def has_permission(self, request, view):
        return not is_device(request.user) and request.user.is_authenticated and request.user.is_superuser

class RegionSerializer(serializers.ModelSerializer):
    def validate(self, data):
        obj = self.instance
        def value(k):
            return data.get(k, getattr(obj, k, None))
        import math
        for key in ['min_lat','max_lat','min_lon','max_lon']:
            val = value(key)
            limit = 90 if 'lat' in key else 180
            if val is None or not math.isfinite(val) or not -limit <= val <= limit:
                raise serializers.ValidationError('Finite valid bounds required.')
        if value('min_lat') >= value('max_lat') or value('min_lon') >= value('max_lon'):
            raise serializers.ValidationError('Minimum bounds must precede maximum bounds.')
        return data
    class Meta:
        model = Region
        fields = ['id','name','enabled','min_lat','max_lat','min_lon','max_lon','ems_mode','provider_key']
        read_only_fields = ['id']

class TeamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Team
        fields = ['id','name','region','available','on_duty','qualifications','members']
        read_only_fields = ['id']

class FacilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Facility
        fields = ['id','name','region','enabled','capacity','suitability']
        read_only_fields = ['id']

class CoordinatorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Coordinator
        fields = ['id','user','region']
        read_only_fields = ['id']

class ConfigView(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    permission_classes = [ConfigurationAdmin]
    @transaction.atomic
    def perform_create(self, serializer):
        obj = serializer.save()
        audit(self.request.user, 'configuration.created', obj, model=obj._meta.label)
    @transaction.atomic
    def perform_update(self, serializer):
        # Changing region associations of operational records requires a future
        # migration workflow, not an ordinary config edit.
        if 'region' in serializer.validated_data and serializer.validated_data['region'] != getattr(serializer.instance, 'region', None):
            raise ValidationError('Region association is immutable.')
        obj = serializer.save()
        audit(self.request.user, 'configuration.updated', obj, model=obj._meta.label)
    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        for obj in self.paginate_queryset(self.get_queryset()):
            audit(request.user, 'configuration.read', obj, model=obj._meta.label)
        return response
    def retrieve(self, request, *args, **kwargs):
        obj = self.get_object()
        audit(request.user, 'configuration.read', obj, model=obj._meta.label)
        return Response(self.get_serializer(obj).data)

class RegionView(ConfigView):
    queryset = Region.objects.all().order_by('name')
    serializer_class = RegionSerializer

class TeamView(ConfigView):
    queryset = Team.objects.all().order_by('name')
    serializer_class = TeamSerializer

class FacilityView(ConfigView):
    queryset = Facility.objects.all().order_by('name')
    serializer_class = FacilitySerializer

class CoordinatorView(ConfigView):
    queryset = Coordinator.objects.all().order_by('created_at')
    serializer_class = CoordinatorSerializer

class EntitlementSerializer(serializers.ModelSerializer):
    household = serializers.PrimaryKeyRelatedField(queryset=Household.objects.all(), validators=[])
    def validate(self, data):
        if data['ends_at'] <= data['starts_at']:
            raise serializers.ValidationError('End must follow start.')
        return data
    class Meta:
        model = Entitlement
        fields = ['household','active','starts_at','ends_at']

class EntitlementView(viewsets.GenericViewSet):
    permission_classes = [ConfigurationAdmin]
    @transaction.atomic
    def create(self, request):
        serializer = EntitlementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        household = Household.objects.select_for_update().get(pk=data.pop('household').id)
        obj, _ = Entitlement.objects.update_or_create(household=household, defaults={**data, 'source': 'manual-sandbox'})
        audit(request.user, 'entitlement.configured', obj, active=obj.active)
        return Response(EntitlementSerializer(obj).data)

class UnroutedView(viewsets.GenericViewSet):
    permission_classes = [ConfigurationAdmin]
    def list(self, request):
        from incidents.models import Incident, OPEN_STATES
        objects = Incident.objects.filter(region__isnull=True, state__in=OPEN_STATES).order_by('accepted_at')[:50]
        # Operational IDs and location quality only, no child content.
        return Response({'results': [{'id': obj.id, 'location_quality': obj.location_quality, 'accepted_at': obj.accepted_at} for obj in objects]})
    @action(detail=True, methods=['post'])
    @transaction.atomic
    def route(self, request, pk=None):
        class Input(serializers.Serializer):
            region = serializers.PrimaryKeyRelatedField(queryset=Region.objects.filter(enabled=True))
            location_verified = serializers.BooleanField()
        serializer = Input(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not serializer.validated_data['location_verified']:
            raise ValidationError('Operator must verify incident location and regional responsibility.')
        from incidents.services import lock_incident
        from incidents.models import OPEN_STATES
        obj = lock_incident(pk)
        if obj.region_id or obj.state not in OPEN_STATES:
            raise ValidationError('Only open unrouted incidents may use this workflow.')
        obj.region = serializer.validated_data['region']
        obj.save(update_fields=['region'])
        audit(request.user, 'incident.region_verified', obj, region_id=str(obj.region_id))
        return Response({'id': obj.id, 'region': obj.region_id})
