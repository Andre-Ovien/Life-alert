from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch
from django.db import connection, connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from common.models import AuditEvent
from . import tests as fixtures
from . import services, workflow
from .adapters import SimulatedNotifications, RetryableNotificationFailure
from .models import (NotificationJob, NotificationAttempt, ResponseEscalation,
                     SimulatedDeliveryReceipt, Notification, Assignment)

class WorkflowTests(TestCase):
    setUp = fixtures.FoundationTests.setUp
    accept = fixtures.FoundationTests.accept
    triage = fixtures.FoundationTests.triage
    as_user = fixtures.FoundationTests.as_user

    def test_acceptance_persists_jobs_without_parent_ack(self):
        obj = self.accept()
        self.assertEqual(NotificationJob.objects.filter(notification__incident=obj).count(), 2)
        self.assertEqual(obj.ems.state, 'handoff_pending')
        self.assertFalse(obj.notifications.filter(acknowledged_at__isnull=False).exists())

    @override_settings(SIM_NOTIFICATION_OUTCOME='retryable_failure')
    def test_retry_is_bounded_and_ems_proceeds_independently(self):
        obj = self.accept()
        services.process_simulated_work()
        obj.ems.refresh_from_db()
        self.assertEqual(obj.ems.state, 'provider_acknowledged')
        jobs = list(NotificationJob.objects.all())
        self.assertTrue(all(j.status == 'ready' and j.attempts == 1 for j in jobs))
        workflow.process_notification_jobs(at=min(j.next_attempt_at for j in jobs)-timedelta(seconds=1))
        self.assertEqual(NotificationAttempt.objects.count(), 2)
        with override_settings(SIM_NOTIFICATION_OUTCOME='success'):
            workflow.process_notification_jobs(at=max(j.next_attempt_at for j in jobs)+timedelta(seconds=1))
        self.assertEqual(NotificationJob.objects.filter(status='succeeded').count(), 2)
        self.assertEqual(SimulatedDeliveryReceipt.objects.count(), 2)

    @override_settings(SIM_NOTIFICATION_OUTCOME='retryable_failure', SIM_NOTIFICATION_MAX_ATTEMPTS=2)
    def test_exhaustion_opens_one_durable_task_per_notification(self):
        self.accept()
        workflow.process_notification_jobs()
        workflow.process_notification_jobs(at=timezone.now()+timedelta(minutes=1))
        workflow.process_notification_jobs(at=timezone.now()+timedelta(hours=1))
        self.assertEqual(NotificationJob.objects.filter(status='failed').count(), 2)
        self.assertEqual(ResponseEscalation.objects.filter(kind='notification_failed').count(), 2)
        self.assertEqual(NotificationAttempt.objects.count(), 4)

    @override_settings(SIM_NOTIFICATION_OUTCOME='unknown')
    def test_unknown_outcome_halts_for_review_instead_of_retry(self):
        self.accept()
        workflow.process_notification_jobs()
        workflow.process_notification_jobs(at=timezone.now()+timedelta(days=1))
        self.assertEqual(NotificationJob.objects.filter(status='blocked').count(), 2)
        self.assertEqual(Notification.objects.filter(state='unknown').count(), 2)
        self.assertEqual(NotificationAttempt.objects.count(), 2)
        self.assertEqual(ResponseEscalation.objects.filter(kind='notification_unknown').count(), 2)

    def test_expired_lease_is_reclaimed_and_late_worker_is_fenced(self):
        self.accept()
        job = NotificationJob.objects.first()
        at = timezone.now()
        old_token, notification_id = workflow.claim_job(job.id, at)
        self.assertIsNone(workflow.claim_job(job.id, at))
        new_at = at+timedelta(minutes=5)
        new_token, _ = workflow.claim_job(job.id, new_at)
        self.assertNotEqual(old_token, new_token)
        self.assertFalse(workflow.finish_job(job.id, old_token, 'simulated', new_at))
        SimulatedNotifications().send(notification_id)
        self.assertTrue(workflow.finish_job(job.id, new_token, 'simulated', new_at))
        job.refresh_from_db()
        self.assertEqual(job.status, 'succeeded')
        self.assertEqual(job.attempts, 2)
        self.assertEqual(job.attempt_records.get(number=1).outcome, 'lease_expired')

    def test_crash_after_simulated_effect_recovers_receipt_without_resend(self):
        self.accept()
        job = NotificationJob.objects.first()
        at = timezone.now()
        token, notification_id = workflow.claim_job(job.id, at)
        SimulatedNotifications().send(notification_id)
        self.assertIsNone(workflow.claim_job(job.id, at+timedelta(minutes=5)))
        job.refresh_from_db()
        self.assertEqual(job.status, 'succeeded')
        self.assertEqual(job.last_code, 'receipt_recovered')
        self.assertEqual(job.attempts, 1)
        self.assertFalse(workflow.finish_job(job.id, token, 'simulated'))
        self.assertEqual(SimulatedDeliveryReceipt.objects.count(), 1)

    @override_settings(SIM_NOTIFICATION_MAX_ATTEMPTS=1)
    def test_interruption_at_attempt_limit_blocks_unknown_work(self):
        self.accept()
        job = NotificationJob.objects.first()
        at = timezone.now()
        workflow.claim_job(job.id, at)
        self.assertIsNone(workflow.claim_job(job.id, at+timedelta(minutes=5)))
        job.refresh_from_db()
        self.assertEqual(job.status, 'blocked')
        self.assertEqual(ResponseEscalation.objects.get().kind, 'notification_unknown')

    def test_simulated_delivery_idempotency_key_is_stable(self):
        obj = self.accept()
        notification = obj.notifications.first()
        adapter = SimulatedNotifications()
        adapter.send(notification.id)
        adapter.send(notification.id)
        receipt = SimulatedDeliveryReceipt.objects.get()
        self.assertEqual(receipt.operation_id, notification.id)

    def test_closed_incident_work_is_cancelled_before_adapter(self):
        obj = self.accept()
        services.transition(self.coord, obj.id, 'cancelled', outcome='Reviewed before response')
        workflow.process_notification_jobs()
        self.assertEqual(NotificationJob.objects.filter(status='cancelled').count(), 2)
        self.assertFalse(SimulatedDeliveryReceipt.objects.exists())

    def test_human_acknowledgement_is_preserved_during_delivery(self):
        obj = self.accept()
        notification = services.acknowledge_notification(self.guardian, obj.id, 'guardian')
        workflow.process_notification_jobs()
        notification.refresh_from_db()
        self.assertEqual(notification.state, 'simulated')
        self.assertEqual(notification.acknowledged_by_id, self.guardian.id)
        self.assertIsNotNone(notification.acknowledged_at)
        obj.refresh_from_db()
        self.assertIsNone(obj.coordinator_owner_id)

    def test_legacy_queued_notifications_are_backfilled_idempotently(self):
        self.accept()
        NotificationJob.objects.all().delete()  # Synthetic unattempted test jobs only.
        workflow.process_notification_jobs()
        workflow.process_notification_jobs()
        self.assertEqual(NotificationJob.objects.count(), 2)
        self.assertEqual(SimulatedDeliveryReceipt.objects.count(), 2)

    def test_unexpected_exception_text_is_not_saved_or_logged(self):
        self.accept()
        with patch('incidents.workflow.SimulatedNotifications.send', side_effect=RuntimeError('private-child-data-token')):
            workflow.process_notification_jobs()
        self.assertEqual(NotificationJob.objects.filter(status='blocked').count(), 2)
        self.assertFalse(NotificationJob.objects.filter(last_code__contains='private-child').exists())
        self.assertNotIn('private-child', str(list(AuditEvent.objects.values('facts'))))

    def test_one_failed_job_does_not_block_other_audience(self):
        obj = self.accept()
        guardian_id = obj.notifications.get(audience='guardian').id
        original = SimulatedNotifications.send
        def send(adapter, notification_id):
            if notification_id == guardian_id:
                raise RetryableNotificationFailure()
            return original(adapter, notification_id)
        with patch('incidents.workflow.SimulatedNotifications.send', send):
            workflow.process_notification_jobs()
        self.assertEqual(NotificationJob.objects.get(notification_id=guardian_id).status, 'ready')
        self.assertEqual(NotificationJob.objects.get(notification__audience='coordinator').status, 'succeeded')

    def test_crew_decline_is_durable_and_requires_acknowledged_owner_resolution(self):
        obj = self.accept(); self.triage(obj)
        offer = services.offer_team(self.coord, obj.id, self.team.id, True)
        services.assignment_transition(self.responder, obj.id, offer.id, 'declined', 'Synthetic vehicle failure')
        task = ResponseEscalation.objects.get(kind='crew_declined')
        workflow.escalate(obj, 'crew_declined', 'assignment:'+str(offer.id))
        self.assertEqual(ResponseEscalation.objects.count(), 1)
        with self.assertRaisesMessage(Exception, 'Invalid escalation'):
            workflow.transition_escalation(self.coord, obj.id, task.id, 'resolved', 'not acknowledged')
        workflow.transition_escalation(self.coord, obj.id, task.id, 'acknowledged', 'Arrange another appropriate response')
        services.record_ems(self.coord, obj.id, 'closed', 'No external response outstanding')
        with self.assertRaisesMessage(Exception, 'outstanding response escalations'):
            services.transition(self.coord, obj.id, 'cancelled', outcome='Attempted early close', reconciled=True)
        workflow.transition_escalation(self.coord, obj.id, task.id, 'resolved', 'Approved alternative arranged; verified handover evidence recorded')
        self.assertEqual(obj.progress_notes.count(), 2)
        self.assertEqual(Assignment.objects.get(pk=offer.id).state, 'declined')

    def test_timed_out_offer_opens_task_only_once(self):
        obj = self.accept(); self.triage(obj)
        offer = services.offer_team(self.coord, obj.id, self.team.id, True)
        offer.deadline = timezone.now()-timedelta(seconds=1); offer.save()
        services.process_simulated_work(); services.process_simulated_work()
        self.assertEqual(ResponseEscalation.objects.filter(kind='crew_timed_out').count(), 1)
        self.assertNotIn('on the way', services.public_status(obj)['message'])

    def test_escalation_api_is_region_scoped_and_not_parent_or_child_data(self):
        obj = self.accept(); self.triage(obj)
        task = workflow.escalate(obj, 'notification_unknown', 'synthetic-test-source')
        endpoint = f'/api/v1/incidents/{obj.id}/escalations/'
        self.assertEqual(self.as_user(self.guardian).get(endpoint).status_code, 403)
        self.assertEqual(self.as_user(self.remote_coord).get(endpoint).status_code, 404)
        response = self.as_user(self.coord).get(endpoint)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        transition = f'/api/v1/incidents/{obj.id}/escalation-transition/'
        response = self.client.post(transition, {'escalation': str(task.id), 'target': 'acknowledged', 'note': 'Taking review of this task'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        obj.refresh_from_db()
        self.assertEqual(obj.coordinator_owner_id, self.coord.id)
        self.assertEqual(task.incident_id, obj.id)


    @override_settings(SIMULATED_EMS_OUTCOME='timeout')
    def test_ems_unknown_has_one_durable_review_task_and_requires_reconciliation(self):
        obj=self.accept();services.process_simulated_work();services.process_simulated_work()
        task=ResponseEscalation.objects.get(kind='ems_unknown')
        self.assertEqual(ResponseEscalation.objects.filter(kind='ems_unknown').count(),1)
        services.claim_ownership(self.coord,obj.id)
        services.request_cancellation(self.coord,obj.id)
        services.record_ems(self.coord,obj.id,'closed','Synthetic manual reconciliation, no external action pending')
        with self.assertRaisesMessage(Exception,'outstanding response escalations'):
            services.transition(self.coord,obj.id,'cancelled',outcome='Reviewed cancellation',reconciled=True)
        workflow.transition_escalation(self.coord,obj.id,task.id,'acknowledged','Own EMS reconciliation review')
        workflow.transition_escalation(self.coord,obj.id,task.id,'resolved','Verified disposition recorded; no external action pending')
        services.transition(self.coord,obj.id,'cancelled',outcome='Reviewed cancellation',reconciled=True)


class AdapterBoundaryTests(TransactionTestCase):
    setUp = fixtures.FoundationTests.setUp
    accept = fixtures.FoundationTests.accept
    def test_adapter_executes_outside_worker_transactions(self):
        self.accept()
        original = SimulatedNotifications.send
        observed = []
        def send(adapter, notification_id):
            observed.append(connection.in_atomic_block)
            return original(adapter, notification_id)
        with patch('incidents.workflow.SimulatedNotifications.send', send):
            workflow.process_notification_jobs()
        self.assertEqual(observed, [False, False])


@skipUnless(connection.vendor == 'postgresql', 'Requires PostgreSQL row locking')
class WorkflowConcurrencyTests(TransactionTestCase):
    setUp = fixtures.FoundationTests.setUp
    accept = fixtures.FoundationTests.accept
    def test_workers_cannot_claim_same_unexpired_job(self):
        self.accept()
        job = NotificationJob.objects.first(); barrier = Barrier(2)
        def run():
            try:
                barrier.wait(timeout=10)
                return workflow.claim_job(job.id)
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run) for _ in range(2)]
            claims = [f.result(timeout=20) for f in futures]
        self.assertEqual(sum(c is not None for c in claims), 1)
        self.assertEqual(NotificationAttempt.objects.filter(job=job).count(), 1)

    def test_parallel_workers_produce_one_logical_receipt_per_audience(self):
        self.accept(); barrier = Barrier(2)
        def run():
            try:
                barrier.wait(timeout=10)
                workflow.process_notification_jobs()
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(run) for _ in range(2)]
            for f in futures: f.result(timeout=20)
        self.assertEqual(NotificationJob.objects.filter(status='succeeded').count(), 2)
        self.assertEqual(NotificationAttempt.objects.count(), 2)
        self.assertEqual(SimulatedDeliveryReceipt.objects.count(), 2)
