"""Durable, fenced local notification jobs and human escalation tasks.

Lock order: incident -> job -> notification/attempt. Adapters run outside the
claim/finalize transactions. Only simulated adapters are supported.
"""
import uuid
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError
from common.audit import audit
from .access import require_coordinator
from .adapters import (SimulatedNotifications, RetryableNotificationFailure,
                       UnknownNotificationOutcome, PermanentNotificationFailure)
from .models import (Incident, Notification, NotificationJob, NotificationAttempt,
                     SimulatedDeliveryReceipt, ResponseEscalation, OPEN_STATES)


def escalate(incident, kind, source_key):
    """Caller holds incident lock; unique source makes repeat scans harmless."""
    task, created = ResponseEscalation.objects.get_or_create(source_key=source_key,
        defaults={'incident': incident, 'kind': kind})
    incident.review_required = True
    incident.save(update_fields=['review_required'])
    if created:
        audit(None, 'response.escalation_opened', incident,
              escalation_id=str(task.id), kind=kind)
    return task


def enqueue_notifications(incident):
    for notification in incident.notifications.filter(state='queued'):
        NotificationJob.objects.get_or_create(notification=notification,
            defaults={'max_attempts': settings.SIM_NOTIFICATION_MAX_ATTEMPTS})


def seed_legacy_jobs(at):
    # Includes closed incidents so their unsent work is durably cancelled below.
    for notification in Notification.objects.filter(state='queued', job__isnull=True):
        NotificationJob.objects.get_or_create(notification=notification,
            defaults={'max_attempts': settings.SIM_NOTIFICATION_MAX_ATTEMPTS, 'next_attempt_at': at})


def _locked_job(pk):
    # Read relation first; no job lock is held before the incident lock.
    incident_id = NotificationJob.objects.values_list('notification__incident_id', flat=True).get(pk=pk)
    incident = Incident.objects.select_for_update().get(pk=incident_id)
    job = NotificationJob.objects.select_for_update().get(pk=pk)
    return incident, job


def _stop(job, incident, status, code):
    job.status, job.last_code = status, code
    job.lease_token = None
    job.lease_until = None
    job.save()
    if status in ['blocked', 'failed']:
        notification = job.notification
        notification.state = 'unknown' if status == 'blocked' else 'failed'
        notification.save(update_fields=['state'])
        escalate(incident, 'notification_unknown' if status == 'blocked' else 'notification_failed',
                 'notification:'+str(notification.id))


@transaction.atomic
def claim_job(pk, at=None):
    at = at or timezone.now()
    incident, job = _locked_job(pk)
    if job.status not in ['ready', 'running']:
        return None
    if job.status == 'running' and job.lease_until and job.lease_until > at:
        return None
    if job.status == 'ready' and job.next_attempt_at > at:
        return None
    if incident.state not in OPEN_STATES:
        _stop(job, incident, 'cancelled', 'incident_closed')
        return None
    if job.notification.audience=='crew' and job.notification.context_key.startswith('offer:'):
        from .models import Assignment
        offer_id=job.notification.context_key.split(':',1)[1]
        if not Assignment.objects.filter(pk=offer_id,incident=incident,state='offered',deadline__gt=at).exists():
            _stop(job,incident,'cancelled','offer_no_longer_current')
            return None
    if job.notification.context_key.startswith('handover:'):
        from .models import IncidentHandover
        handover_id=job.notification.context_key.split(':',1)[1]
        if not IncidentHandover.objects.filter(pk=handover_id,incident=incident,status='pending',
                source_owner_id=incident.coordinator_owner_id,source_region_id=incident.region_id).exists():
            _stop(job,incident,'cancelled','handover_no_longer_pending')
            return None
    if job.notification.audience=='crew' and job.notification.context_key.startswith('location:'):
        if not incident.assignments.filter(team_id=job.notification.recipient_team_id,state__in=['accepted','en_route','arrived']).exists():
            _stop(job,incident,'cancelled','assignment_no_longer_active')
            return None
    if job.notification.audience=='coordinator' and job.notification.context_key.startswith('location:'):
        from operations.models import Coordinator
        if not Coordinator.objects.filter(user_id=job.notification.recipient_user_id,region_id=incident.region_id).exists():
            _stop(job,incident,'cancelled','recipient_no_longer_regional')
            return None
    if job.status == 'running':
        NotificationAttempt.objects.filter(job=job, number=job.attempts, outcome='started').update(outcome='lease_expired')
        # The safe simulator can reconcile a committed receipt without sending.
        # A future external provider needs its own verified reconciliation API.
        if SimulatedDeliveryReceipt.objects.filter(notification=job.notification).exists():
            job.notification.state = 'simulated'
            job.notification.save(update_fields=['state'])
            _stop(job, incident, 'succeeded', 'receipt_recovered')
            audit(None, 'notification.receipt_recovered', incident, job_id=str(job.id))
            return None
    if job.attempts >= job.max_attempts:
        _stop(job, incident, 'blocked', 'attempt_limit_after_interruption')
        return None
    job.attempts += 1
    job.status = 'running'
    job.lease_token = uuid.uuid4()
    job.lease_until = at + timedelta(seconds=settings.SIM_NOTIFICATION_LEASE_SECONDS)
    job.last_code = ''
    job.save()
    NotificationAttempt.objects.create(job=job, number=job.attempts, lease_token=job.lease_token)
    audit(None, 'notification.attempt_started', incident, job_id=str(job.id), attempt=job.attempts)
    return job.lease_token, job.notification_id


@transaction.atomic
def finish_job(pk, lease_token, outcome, at=None):
    at = at or timezone.now()
    incident, job = _locked_job(pk)
    if job.status != 'running' or job.lease_token != lease_token:
        return False  # A reclaimed lease fences late/stale workers.
    attempt = NotificationAttempt.objects.get(job=job, number=job.attempts)
    attempt.outcome = outcome
    attempt.save(update_fields=['outcome'])
    if incident.state not in OPEN_STATES:
        _stop(job, incident, 'cancelled', 'incident_closed')
    elif outcome == 'simulated':
        job.notification.state = 'simulated'
        job.notification.save(update_fields=['state'])
        _stop(job, incident, 'succeeded', 'simulated')
    elif outcome == 'retryable_failure' and job.attempts < job.max_attempts:
        job.status = 'ready'
        job.last_code = outcome
        job.lease_token = job.lease_until = None
        job.next_attempt_at = at + timedelta(seconds=settings.SIM_NOTIFICATION_RETRY_SECONDS * 2**(job.attempts-1))
        job.save()
    else:
        _stop(job, incident, 'blocked' if outcome == 'unknown' else 'failed', outcome)
    audit(None, 'notification.attempt_finished', incident,
          job_id=str(job.id), attempt=job.attempts, outcome=outcome)
    return True


def process_notification_jobs(limit=100, at=None):
    at = at or timezone.now()
    seed_legacy_jobs(at)
    due = NotificationJob.objects.filter(
        Q(status='ready', next_attempt_at__lte=at) |
        Q(status='running', lease_until__lte=at)).order_by('next_attempt_at', 'id')
    processed = 0
    for pk in list(due.values_list('id', flat=True)[:limit]):
        claim = claim_job(pk, at)
        if claim is None:
            continue
        token, notification_id = claim
        # No incident/job database lock or transaction spans adapter execution.
        try:
            outcome = SimulatedNotifications().send(notification_id)
        except RetryableNotificationFailure:
            outcome = 'retryable_failure'
        except UnknownNotificationOutcome:
            outcome = 'unknown'
        except PermanentNotificationFailure:
            outcome = 'permanent_failure'
        except Exception:
            # Never store exception strings that might contain sensitive data.
            outcome = 'unknown'
        finish_job(pk, token, outcome, at)
        processed += 1
    return processed


@transaction.atomic
def transition_escalation(actor, incident_id, escalation_id, target, note):
    incident = Incident.objects.select_for_update().get(pk=incident_id)
    require_coordinator(actor, incident)
    task = ResponseEscalation.objects.select_for_update().get(pk=escalation_id, incident=incident)
    allowed = {'open': {'acknowledged'}, 'acknowledged': {'resolved'}}
    if target not in allowed.get(task.status, set()):
        raise ValidationError('Invalid escalation transition.')
    if not note.strip():
        raise ValidationError('Record actions and next steps or resolution evidence.')
    if target == 'resolved' and incident.coordinator_owner_id != actor.pk:
        raise PermissionDenied('Current incident owner must review the solution.')
    if target == 'acknowledged':
        task.acknowledged_by, task.acknowledged_at = actor, timezone.now()
    else:
        task.resolved_at = timezone.now()
    from .models import ProgressNote
    ProgressNote.objects.create(incident=incident, author=actor, action_taken=task.kind+': '+note,
        next_steps='Escalation acknowledged; solution required.' if target == 'acknowledged' else 'Escalation disposition reviewed by current owner.')
    task.status, task.resolution_note = target, note
    task.save()
    audit(actor, 'response.escalation_transition', incident,
          escalation_id=str(task.id), target=target)
    return task
