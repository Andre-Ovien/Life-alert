from django.conf import settings
from django.db import models
from common.models import Record

class Region(Record):
    name = models.CharField(max_length=120)
    enabled = models.BooleanField(default=False)
    # Rectangular pilot boundaries only; replace with reviewed PostGIS polygons.
    min_lat = models.FloatField()
    max_lat = models.FloatField()
    min_lon = models.FloatField()
    max_lon = models.FloatField()
    ems_mode = models.CharField(max_length=30, choices=[('manual', 'Coordinator handoff'), ('simulated', 'Simulated')], default='manual')
    provider_key = models.CharField(max_length=100, blank=True)
    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(min_lat__gte=-90, max_lat__lte=90, min_lat__lt=models.F('max_lat')), name='valid_lat_bounds'),
            models.CheckConstraint(condition=models.Q(min_lon__gte=-180, max_lon__lte=180, min_lon__lt=models.F('max_lon')), name='valid_lon_bounds'),
        ]

class Coordinator(Record):
    on_duty = models.BooleanField(default=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    region = models.ForeignKey(Region, on_delete=models.PROTECT)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'region'], name='unique_regional_coordinator')]

class Team(Record):
    region = models.ForeignKey(Region, on_delete=models.PROTECT)
    name = models.CharField(max_length=120)
    on_duty = models.BooleanField(default=False)
    available = models.BooleanField(default=False)
    qualifications = models.JSONField(default=list)
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True)

class Facility(Record):
    region = models.ForeignKey(Region, on_delete=models.PROTECT)
    name = models.CharField(max_length=120)
    enabled = models.BooleanField(default=False)
    reservation_seconds=models.PositiveIntegerField(null=True)
    capacity = models.PositiveIntegerField(default=0)
    suitability = models.TextField(blank=True)

class ResponsePolicy(Record):
    region = models.OneToOneField(Region,on_delete=models.PROTECT,related_name='response_policy')
    enabled = models.BooleanField(default=False)
    primary = models.ForeignKey(Coordinator,null=True,on_delete=models.PROTECT,related_name='primary_policies')
    backup = models.ForeignKey(Coordinator,null=True,on_delete=models.PROTECT,related_name='backup_policies')
    ownership_seconds = models.PositiveIntegerField(null=True)
    offer_seconds = models.PositiveIntegerField(null=True)
    review_reference = models.CharField(max_length=200,blank=True)

class CarePlace(Record):
    facility=models.ForeignKey(Facility,on_delete=models.PROTECT,related_name='places')
    label=models.CharField(max_length=100)
    enabled=models.BooleanField(default=False)
    suitability=models.TextField(blank=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['facility','label'],name='unique_facility_place_label')]

class FacilityStaff(Record):
    facility=models.ForeignKey(Facility,on_delete=models.PROTECT)
    user=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    active=models.BooleanField(default=False)
    on_duty=models.BooleanField(default=False)
    review_reference=models.CharField(max_length=200,blank=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['facility','user'],name='unique_facility_staff')]
