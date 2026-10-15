from django.db import models
from django.conf import settings
from common.models import Record

OPEN_STATES = ['received', 'triage', 'active']

class Incident(Record):
    child = models.ForeignKey('families.Child', on_delete=models.PROTECT)
    region = models.ForeignKey('operations.Region', null=True, on_delete=models.PROTECT)
    state = models.CharField(max_length=20, choices=[(s, s) for s in OPEN_STATES + ['resolved', 'cancelled']], default='received')
    coordinator_owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name='owned_incidents')
    accepted_at = models.DateTimeField()
    accepted_entitlement_until = models.DateTimeField()
    location = models.JSONField(default=dict)
    location_quality = models.CharField(max_length=30)
    saved_address_fallback = models.TextField(blank=True)
    response_started_at = models.DateTimeField(null=True)
    review_required = models.BooleanField(default=False)
    cancellation_requested = models.BooleanField(default=False)
    outcome = models.TextField(blank=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['child'], condition=models.Q(state__in=OPEN_STATES), name='one_open_incident_per_child')]

class HelpRequest(Record):
    child = models.ForeignKey('families.Child', on_delete=models.PROTECT)
    key = models.UUIDField()
    fingerprint = models.CharField(max_length=64)
    location = models.JSONField(default=dict)
    incident = models.ForeignKey(Incident, on_delete=models.PROTECT)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['child', 'key'], name='idempotent_child_request')]

class Assignment(Record):
    incident = models.ForeignKey(Incident, on_delete=models.PROTECT, related_name='assignments')
    team = models.ForeignKey('operations.Team', on_delete=models.PROTECT)
    state = models.CharField(max_length=20, choices=[(s, s) for s in ['offered', 'accepted', 'en_route', 'arrived', 'complete', 'declined', 'timed_out']], default='offered')
    deadline = models.DateTimeField()
    decline_reason = models.CharField(max_length=500, blank=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['incident'], condition=models.Q(state__in=['offered', 'accepted', 'en_route', 'arrived']), name='one_live_assignment')]

class EMSOperation(Record):
    incident = models.OneToOneField(Incident, on_delete=models.PROTECT, related_name='ems')
    state = models.CharField(max_length=30, choices=[(s, s) for s in ['handoff_pending', 'provider_acknowledged', 'unknown', 'contact_confirmed', 'dispatch_confirmed', 'arrived', 'no_dispatch', 'closed']], default='handoff_pending')
    evidence = models.TextField(blank=True)

class Notification(Record):
    incident = models.ForeignKey(Incident, on_delete=models.PROTECT, related_name='notifications')
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledged_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    audience = models.CharField(max_length=20, choices=[('guardian', 'guardian'), ('coordinator', 'coordinator')])
    state = models.CharField(max_length=20, choices=[(s, s) for s in ['queued', 'simulated', 'delivered', 'failed']], default='queued')
    class Meta:
        constraints = [models.UniqueConstraint(fields=['incident', 'audience'], name='unique_notification_audience')]

class Placement(Record):
    incident = models.ForeignKey(Incident, on_delete=models.PROTECT, related_name='placements')
    facility = models.ForeignKey('operations.Facility', on_delete=models.PROTECT)
    state = models.CharField(max_length=20, choices=[(s, s) for s in ['reserved', 'intake', 'released', 'cancelled']], default='reserved')
    authority_reference = models.CharField(max_length=200)
    staff = models.ManyToManyField('auth.User', blank=True)
    handover_reference = models.CharField(max_length=200, blank=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['incident'], condition=models.Q(state__in=['reserved', 'intake']), name='one_live_placement')]

class ProgressNote(Record):
    incident = models.ForeignKey(Incident, on_delete=models.PROTECT, related_name='progress_notes')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action_taken = models.TextField()
    next_steps = models.TextField()
