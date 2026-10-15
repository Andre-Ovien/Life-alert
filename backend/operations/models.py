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
    capacity = models.PositiveIntegerField(default=0)
    suitability = models.TextField(blank=True)
