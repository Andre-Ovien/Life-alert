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
    class Meta:
        permissions = [("read_audit_events", "Read structural audit events for security review")]

class AdultTokenSession(Record):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    access_digest = models.CharField(max_length=64, unique=True)
    refresh_digest = models.CharField(max_length=64, unique=True)
    access_expires_at = models.DateTimeField()
    refresh_expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True)
    mfa_verified_at = models.DateTimeField(null=True)

class UsedRefreshToken(Record):
    session = models.ForeignKey(AdultTokenSession, on_delete=models.PROTECT)
    digest = models.CharField(max_length=64, unique=True)

class AccountChallenge(Record):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    purpose = models.CharField(max_length=20, choices=[('recovery','recovery'),('contact','contact')])
    digest = models.CharField(max_length=64, unique=True)
    target_email = models.EmailField()
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True)

class VerifiedContact(Record):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    email = models.EmailField()
    verified_at = models.DateTimeField()
    class Meta:
        constraints = [models.UniqueConstraint(fields=['user','email'], name='unique_verified_contact')]

class IdentityDispatch(Record):
    challenge = models.OneToOneField(AccountChallenge, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, default='simulated')

class PrivacyRequest(Record):
    requester=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='privacy_requests')
    request_id=models.UUIDField()
    kind=models.CharField(max_length=20,choices=[(s,s) for s in ['export','correction','media_delete','account_close']])
    child=models.ForeignKey('families.Child',null=True,on_delete=models.PROTECT)
    media=models.ForeignKey('families.CareMedia',null=True,on_delete=models.PROTECT)
    details=models.TextField(blank=True)
    fingerprint=models.CharField(max_length=64)
    status=models.CharField(max_length=20,default='submitted',choices=[(s,s) for s in ['submitted','approved','hold','denied','processing','fulfilled']])
    reviewer=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.PROTECT)
    review_reference=models.CharField(max_length=200,blank=True)
    purge_after=models.DateTimeField(null=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['requester','request_id'],name='unique_privacy_request')]
        permissions=[('review_privacyrequest','Review purpose-scoped privacy requests')]

class RetentionPolicy(Record):
    purpose=models.CharField(max_length=30,unique=True,default='media')
    enabled=models.BooleanField(default=False)
    minimum_seconds=models.PositiveIntegerField(null=True)
    review_reference=models.CharField(max_length=200,blank=True)

class PrivacyDecision(Record):
    request=models.ForeignKey(PrivacyRequest,on_delete=models.PROTECT,related_name='decisions')
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    decision=models.CharField(max_length=40)
    reference=models.CharField(max_length=200)

class StaffMFA(Record):
    user=models.OneToOneField(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    encrypted_secret=models.TextField()
    enrollment_expires_at=models.DateTimeField()
    confirmed_at=models.DateTimeField(null=True)
    last_step=models.BigIntegerField(default=-1)
    recovery_digests=models.JSONField(default=list)
