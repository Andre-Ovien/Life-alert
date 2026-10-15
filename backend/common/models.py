import uuid
from django.conf import settings
from django.db import models

class Record(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        abstract = True

class AuditEvent(Record):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    device_id = models.UUIDField(null=True)
    action = models.CharField(max_length=80)
    object_id = models.UUIDField()
    # Controlled structural facts only; never arbitrary request payloads.
    facts = models.JSONField(default=dict)
