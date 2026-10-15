from django.conf import settings
from django.db import models
from common.models import Record

class Household(Record):
    name = models.CharField(max_length=120)

class Guardian(Record):
    household = models.ForeignKey(Household, on_delete=models.PROTECT, related_name='guardians')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['household', 'user'], name='unique_guardian')]

class Child(Record):
    household = models.ForeignKey(Household, on_delete=models.PROTECT, related_name='children')
    name = models.CharField(max_length=120)
    current_version = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    communication = models.TextField(blank=True)
    support_needs = models.TextField(blank=True)
    calming_preferences = models.TextField(blank=True)
    saved_address = models.TextField(blank=True)

class EmergencyContact(Record):
    child = models.ForeignKey(Child, on_delete=models.PROTECT, related_name='contacts')
    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=40)
    relationship = models.CharField(max_length=100, blank=True)
    active = models.BooleanField(default=True)
    # Not an assertion of care/release authority.

class Device(Record):
    child = models.ForeignKey(Child, on_delete=models.PROTECT, related_name='devices')
    label = models.CharField(max_length=100)
    token_digest = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField(null=True)
    rotated_from = models.ForeignKey('self',null=True,on_delete=models.PROTECT)
    revoked_at = models.DateTimeField(null=True, blank=True)

class CareMedia(Record):
    archived_at=models.DateTimeField(null=True)
    legal_hold=models.BooleanField(default=False)
    retention_until=models.DateTimeField(null=True)
    child = models.ForeignKey(Child, on_delete=models.PROTECT, related_name='media')
    title = models.CharField(max_length=120)
    for_child = models.BooleanField(default=False)
    for_responder = models.BooleanField(default=False)
    instructions_text = models.TextField(blank=True)
    file = models.FileField(upload_to='care/%Y/%m/', blank=True)
    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(for_child=True) | models.Q(for_responder=True), name='media_has_audience')]

class Entitlement(Record):
    # A single local ledger row, later reconciled by a billing adapter.
    household = models.OneToOneField(Household, on_delete=models.PROTECT, related_name='entitlement')
    active = models.BooleanField(default=False)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    source = models.CharField(max_length=80, default='manual-sandbox')
    billing_revision = models.PositiveBigIntegerField(default=0)
    billing_fingerprint = models.CharField(max_length=64, blank=True)
    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(ends_at__gt=models.F('starts_at')), name='entitlement_valid_interval')]

    def eligible(self, at):
        return self.active and self.starts_at <= at < self.ends_at

class CaregiverGrant(Record):
    child = models.ForeignKey(Child, on_delete=models.PROTECT, related_name='caregiver_grants')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='caregiver_grants')
    relationship = models.CharField(max_length=120)
    can_view_care = models.BooleanField(default=False)
    can_view_incidents = models.BooleanField(default=False)
    can_request_help = models.BooleanField(default=False)
    can_manage_profile = models.BooleanField(default=False)
    can_manage_media = models.BooleanField(default=False)
    can_manage_devices = models.BooleanField(default=False)
    expires_at = models.DateTimeField(null=True)
    revoked_at = models.DateTimeField(null=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['child', 'user'], name='unique_caregiver_child')]

class CaregiverInvitation(Record):
    child = models.ForeignKey(Child, on_delete=models.PROTECT)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='care_invitations')
    inviter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    relationship = models.CharField(max_length=120)
    permissions = models.JSONField(default=list)
    token_digest = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    status = models.CharField(max_length=20, default='pending', choices=[(s,s) for s in ['pending','accepted','declined','revoked']])

class CareVersion(Record):
    child = models.ForeignKey(Child, on_delete=models.PROTECT, related_name='care_versions')
    number = models.PositiveIntegerField()
    payload = models.JSONField()
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['child','number'], name='unique_child_care_version')]

class SavedPlace(Record):
    child = models.ForeignKey(Child, on_delete=models.PROTECT, related_name='places')
    label = models.CharField(max_length=120)
    address = models.TextField()
    is_default = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['child'], condition=models.Q(is_default=True,active=True), name='one_default_saved_place')]

class AuthorityRecord(Record):
    child = models.ForeignKey(Child, on_delete=models.PROTECT, related_name='authority_records')
    subject = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='care_authorities')
    purpose = models.CharField(max_length=20, choices=[('placement','placement'),('release','release')])
    status = models.CharField(max_length=20, default='pending', choices=[('pending','pending'),('verified','verified'),('revoked','revoked')])
    evidence_reference = models.CharField(max_length=200)
    verification_reference = models.CharField(max_length=200, blank=True)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    verified_at = models.DateTimeField(null=True)
    valid_until = models.DateTimeField(null=True)

class DeviceLinkChallenge(Record):
    child = models.ForeignKey(Child, on_delete=models.PROTECT)
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    label = models.CharField(max_length=100)
    digest = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True)
    revoked_at = models.DateTimeField(null=True)

class BillingEvent(Record):
    household = models.ForeignKey(Household, on_delete=models.PROTECT)
    provider = models.CharField(max_length=40, default='sandbox')
    event_id = models.CharField(max_length=120)
    revision = models.PositiveBigIntegerField()
    fingerprint = models.CharField(max_length=64)
    status = models.CharField(max_length=20, choices=[('applied','applied'),('ignored','ignored'),('conflict','conflict')])
    class Meta:
        constraints = [models.UniqueConstraint(fields=['provider','event_id'], name='unique_billing_provider_event')]

class RetiredMediaBlob(Record):
    media=models.ForeignKey(CareMedia,on_delete=models.PROTECT)
    storage_name=models.CharField(max_length=500)
    purge_after=models.DateTimeField(null=True)
    purged_at=models.DateTimeField(null=True)
