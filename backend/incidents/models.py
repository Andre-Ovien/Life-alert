from django.db import models
from django.conf import settings
from django.utils import timezone
from common.models import Record

OPEN_STATES = ['received', 'triage', 'active']

class Incident(Record):
    child = models.ForeignKey('families.Child', on_delete=models.PROTECT)
    region = models.ForeignKey('operations.Region', null=True, on_delete=models.PROTECT)
    care_version = models.ForeignKey('families.CareVersion', null=True, on_delete=models.PROTECT)
    state = models.CharField(max_length=20, choices=[(s, s) for s in OPEN_STATES + ['resolved', 'cancelled']], default='received')
    coordinator_owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name='owned_incidents')
    accepted_at = models.DateTimeField()
    accepted_entitlement_until = models.DateTimeField()
    location_revision = models.PositiveIntegerField(default=0)
    location = models.JSONField(default=dict)
    location_quality = models.CharField(max_length=30)
    saved_address_fallback = models.TextField(blank=True)
    response_started_at = models.DateTimeField(null=True)
    review_required = models.BooleanField(default=False)
    cancellation_requested = models.BooleanField(default=False)
    outcome = models.TextField(blank=True)
    outcome_details=models.JSONField(default=dict)
    closed_at=models.DateTimeField(null=True)
    closed_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.PROTECT,related_name='closed_incidents')
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
    context_key = models.CharField(max_length=120,blank=True,default='')
    recipient_user = models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.PROTECT,related_name='response_notifications')
    recipient_team = models.ForeignKey('operations.Team',null=True,on_delete=models.PROTECT)
    audience = models.CharField(max_length=20, choices=[(s,s) for s in ['guardian','coordinator','crew','backup']])
    state = models.CharField(max_length=20, choices=[(s, s) for s in ['queued', 'simulated', 'delivered', 'failed', 'unknown']], default='queued')
    class Meta:
        constraints = [models.UniqueConstraint(fields=['incident','audience','context_key'], name='unique_notification_context')]

class Placement(Record):
    incident = models.ForeignKey(Incident, on_delete=models.PROTECT, related_name='placements')
    facility = models.ForeignKey('operations.Facility', on_delete=models.PROTECT)
    state = models.CharField(max_length=20, choices=[(s, s) for s in ['reserved', 'intake', 'released', 'cancelled']], default='reserved')
    authority_reference = models.CharField(max_length=200)
    authority=models.ForeignKey('families.AuthorityRecord',null=True,on_delete=models.PROTECT)
    care_place=models.ForeignKey('operations.CarePlace',null=True,on_delete=models.PROTECT)
    reserved_until=models.DateTimeField(null=True)
    intake_at=models.DateTimeField(null=True)
    released_at=models.DateTimeField(null=True)
    current_staff=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.PROTECT,related_name='owned_placements')
    transport_reference=models.CharField(max_length=200,blank=True)
    intake_reference=models.CharField(max_length=200,blank=True)
    belongings=models.JSONField(default=list)
    staff = models.ManyToManyField('auth.User', blank=True)
    handover_reference = models.CharField(max_length=200, blank=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['incident'], condition=models.Q(state__in=['reserved', 'intake']), name='one_live_placement'),
            models.UniqueConstraint(fields=['care_place'],condition=models.Q(state__in=['reserved','intake'],care_place__isnull=False),name='one_live_care_place')]

class ProgressNote(Record):
    incident = models.ForeignKey(Incident, on_delete=models.PROTECT, related_name='progress_notes')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action_taken = models.TextField()
    next_steps = models.TextField()

class NotificationJob(Record):
    """Durable local-simulation work; no recipient data or arbitrary payload."""
    notification = models.OneToOneField(Notification, on_delete=models.PROTECT, related_name='job')
    status = models.CharField(max_length=20, default='ready', choices=[(s, s) for s in ['ready', 'running', 'succeeded', 'failed', 'blocked', 'cancelled']])
    attempts = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=3)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    lease_until = models.DateTimeField(null=True)
    lease_token = models.UUIDField(null=True)
    last_code = models.CharField(max_length=40, blank=True)
    class Meta:
        indexes = [models.Index(fields=['status', 'next_attempt_at'])]
        constraints = [models.CheckConstraint(condition=models.Q(max_attempts__gte=1), name='notification_max_attempts_positive')]

class NotificationAttempt(Record):
    job = models.ForeignKey(NotificationJob, on_delete=models.PROTECT, related_name='attempt_records')
    number = models.PositiveIntegerField()
    lease_token = models.UUIDField()
    outcome = models.CharField(max_length=30, default='started')
    class Meta:
        constraints = [models.UniqueConstraint(fields=['job', 'number'], name='unique_notification_attempt')]

class SimulatedDeliveryReceipt(Record):
    notification = models.OneToOneField(Notification, on_delete=models.PROTECT)
    # Stable ID reused across retries; stands in for a provider idempotency key.
    operation_id = models.UUIDField(unique=True)

class ResponseEscalation(Record):
    incident = models.ForeignKey(Incident, on_delete=models.PROTECT, related_name='escalations')
    source_key = models.CharField(max_length=100, unique=True)
    kind = models.CharField(max_length=30, choices=[(s, s) for s in ['crew_declined', 'crew_timed_out', 'notification_failed', 'notification_unknown','coordinator_unclaimed','crew_exhausted','care_changed','care_capacity','location_changed','region_review','reservation_expired','care_handover','ems_unknown']])
    status = models.CharField(max_length=20, default='open', choices=[(s, s) for s in ['open', 'acknowledged', 'resolved']])
    acknowledged_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    acknowledged_at = models.DateTimeField(null=True)
    resolved_at = models.DateTimeField(null=True)
    resolution_note = models.TextField(blank=True)

class ResponsePlan(Record):
    incident = models.OneToOneField(Incident,on_delete=models.PROTECT,related_name='response_plan')
    enabled = models.BooleanField(default=False)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    revision = models.PositiveIntegerField(default=1)
    reviewed_location_revision = models.PositiveIntegerField(default=0)
    reviewed_care_version = models.PositiveIntegerField()
    review_reference = models.CharField(max_length=200)

class ApprovedCrewCandidate(Record):
    plan = models.ForeignKey(ResponsePlan,on_delete=models.PROTECT,related_name='candidates')
    team = models.ForeignKey('operations.Team',on_delete=models.PROTECT)
    priority = models.PositiveIntegerField()
    class Meta:
        constraints=[models.UniqueConstraint(fields=['plan','team'],name='unique_approved_team'),
            models.UniqueConstraint(fields=['plan','priority'],name='unique_candidate_priority')]

class ResponsePlanReview(Record):
    plan=models.ForeignKey(ResponsePlan,on_delete=models.PROTECT)
    revision=models.PositiveIntegerField()
    reviewer=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    review_reference=models.CharField(max_length=200)
    candidate_ids=models.JSONField(default=list)
    care_version=models.PositiveIntegerField()
    class Meta:
        constraints=[models.UniqueConstraint(fields=['plan','revision'],name='unique_response_plan_review')]

class LocationUpdate(Record):
    incident=models.ForeignKey(Incident,on_delete=models.PROTECT,related_name='location_updates')
    request_id=models.UUIDField()
    fingerprint=models.CharField(max_length=64)
    location=models.JSONField(default=dict)
    quality=models.CharField(max_length=30)
    matched_region=models.ForeignKey('operations.Region',null=True,on_delete=models.PROTECT)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.PROTECT,related_name='reported_locations')
    device_id=models.UUIDField(null=True)
    status=models.CharField(max_length=20,default='pending',choices=[('pending','pending'),('verified','verified'),('rejected','rejected')])
    reviewed_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.PROTECT)
    review_reference=models.CharField(max_length=200,blank=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['incident','request_id'],name='unique_incident_location_request')]

class IncidentHandover(Record):
    incident=models.ForeignKey(Incident,on_delete=models.PROTECT)
    source_region=models.ForeignKey('operations.Region',on_delete=models.PROTECT,related_name='outgoing_handovers')
    target=models.ForeignKey('operations.Coordinator',on_delete=models.PROTECT,related_name='incoming_handovers')
    source_owner=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    reference=models.CharField(max_length=200)
    status=models.CharField(max_length=20,default='pending',choices=[('pending','pending'),('accepted','accepted'),('cancelled','cancelled'),('declined','declined')])
    accepted_at=models.DateTimeField(null=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['incident'],condition=models.Q(status='pending'),name='one_pending_region_handover')]

class EMSEvidenceEvent(Record):
    operation=models.ForeignKey(EMSOperation,on_delete=models.PROTECT,related_name='events')
    event_id=models.UUIDField()
    fingerprint=models.CharField(max_length=64)
    state=models.CharField(max_length=30)
    evidence=models.TextField()
    observed_at=models.DateTimeField()
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.PROTECT)
    source=models.CharField(max_length=20,default='manual')
    class Meta:
        constraints=[models.UniqueConstraint(fields=['operation','event_id'],name='unique_ems_evidence_event')]

class CareHandover(Record):
    placement=models.ForeignKey(Placement,on_delete=models.PROTECT,related_name='handovers')
    kind=models.CharField(max_length=20,choices=[('intake','intake'),('shift','shift'),('release','release')])
    source=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.PROTECT,related_name='outgoing_care_handovers')
    recipient=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='incoming_care_handovers')
    author=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    status=models.CharField(max_length=20,default='pending',choices=[('pending','pending'),('accepted','accepted'),('cancelled','cancelled'),('declined','declined')])
    reference=models.CharField(max_length=200)
    accepted_at=models.DateTimeField(null=True)
    authority=models.ForeignKey('families.AuthorityRecord',null=True,on_delete=models.PROTECT)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['placement'],condition=models.Q(status='pending'),name='one_pending_care_handover')]

class CareEvent(Record):
    placement=models.ForeignKey(Placement,on_delete=models.PROTECT,related_name='care_events')
    event_id=models.UUIDField()
    author=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    kind=models.CharField(max_length=30,choices=[(s,s) for s in ['support','observation','handover_note']])
    note=models.TextField()
    fingerprint=models.CharField(max_length=64)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['placement','event_id'],name='unique_placement_care_event')]
