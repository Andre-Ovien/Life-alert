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
    communication = models.TextField(blank=True)
    support_needs = models.TextField(blank=True)
    calming_preferences = models.TextField(blank=True)
    saved_address = models.TextField(blank=True)

class EmergencyContact(Record):
    child = models.ForeignKey(Child, on_delete=models.PROTECT, related_name='contacts')
    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=40)
    relationship = models.CharField(max_length=100, blank=True)
    # Not an assertion of care/release authority.

class Device(Record):
    child = models.ForeignKey(Child, on_delete=models.PROTECT, related_name='devices')
    label = models.CharField(max_length=100)
    token_digest = models.CharField(max_length=64, unique=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

class CareMedia(Record):
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
    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(ends_at__gt=models.F('starts_at')), name='entitlement_valid_interval')]

    def eligible(self, at):
        return self.active and self.starts_at <= at < self.ends_at
