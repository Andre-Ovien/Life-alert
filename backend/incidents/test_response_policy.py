from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from django.db import connection,connections
from django.test import TestCase,TransactionTestCase
from django.utils import timezone
from incidents import tests as fixtures
from operations.models import ResponsePolicy,Coordinator,Team
from families.services import update_profile
from . import services
from .response_policy import configure_plan,tick_response_policy
from .models import Assignment,Notification,ResponseEscalation,ResponsePlanReview,NotificationJob
from .workflow import process_notification_jobs

class PolicySetup:
    def policy(self,enabled=True):
        primary=Coordinator.objects.get(user=self.coord,region=self.region)
        primary.on_duty=True;primary.save()
        backup=Coordinator.objects.create(user=self.remote_coord,region=self.region,on_duty=True)
        return ResponsePolicy.objects.create(region=self.region,enabled=enabled,primary=primary,backup=backup,
            ownership_seconds=30,offer_seconds=45,review_reference='Synthetic reviewed policy - not a service promise')
    def reviewed_plan(self,obj,teams=None):
        services.claim_ownership(self.coord,obj.id)
        return configure_plan(self.coord,obj.id,True,teams or [self.team.id],'Synthetic individual suitability review')

class ResponsePolicyTests(PolicySetup,TestCase):
    setUp=fixtures.FoundationTests.setUp
    accept=fixtures.FoundationTests.accept
    as_user=fixtures.FoundationTests.as_user
    def test_disabled_policy_never_auto_offers(self):
        obj=self.accept();self.policy(False);self.reviewed_plan(obj)
        tick_response_policy(obj.id)
        self.assertFalse(Assignment.objects.exists())
        self.assertFalse(Notification.objects.filter(context_key='policy-primary').exists())

    def test_enabled_policy_offers_only_reviewed_current_candidate(self):
        obj=self.accept();self.policy();self.reviewed_plan(obj)
        tick_response_policy(obj.id);tick_response_policy(obj.id)
        offer=Assignment.objects.get()
        self.assertEqual(offer.team_id,self.team.id);self.assertEqual(offer.state,'offered')
        self.assertEqual(Notification.objects.filter(audience='crew').count(),1)
        self.assertEqual(NotificationJob.objects.filter(notification__audience='crew').count(),1)
        obj.refresh_from_db();self.assertNotIn('on the way',services.public_status(obj)['message'])

    def test_decline_moves_to_next_approved_available_team(self):
        obj=self.accept();self.policy()
        second=Team.objects.create(region=self.region,name='Second synthetic team',available=True,on_duty=True)
        second.members.add(self.other)
        self.reviewed_plan(obj,[self.team.id,second.id]);tick_response_policy(obj.id)
        first=Assignment.objects.get()
        services.assignment_transition(self.responder,obj.id,first.id,'declined','Synthetic unavailable vehicle')
        tick_response_policy(obj.id)
        second_offer=Assignment.objects.get(state='offered')
        self.assertEqual(second_offer.team_id,second.id)
        self.assertEqual(ResponseEscalation.objects.filter(kind='crew_declined').count(),1)

    def test_no_candidates_and_unclaimed_coordinator_open_durable_backup_work(self):
        obj=self.accept();self.policy()
        tick_response_policy(obj.id,at=obj.accepted_at+timedelta(seconds=31))
        self.assertEqual(ResponseEscalation.objects.get().kind,'coordinator_unclaimed')
        self.assertEqual(Notification.objects.filter(audience='backup').count(),1)
        self.assertIsNone(obj.coordinator_owner_id)
        services.acknowledge_notification(self.coord,obj.id,'coordinator')
        tick_response_policy(obj.id,at=obj.accepted_at+timedelta(minutes=1))
        self.assertEqual(Notification.objects.filter(audience='backup').count(),1)
        self.reviewed_plan(obj)
        self.team.available=False;self.team.save()
        tick_response_policy(obj.id)
        self.assertTrue(ResponseEscalation.objects.filter(kind='crew_exhausted').exists())
        self.assertFalse(Assignment.objects.exists())

    def test_changed_care_requires_new_review_and_preserves_review_history(self):
        obj=self.accept();self.policy();self.reviewed_plan(obj)
        self.child.refresh_from_db()
        update_profile(self.guardian,self.child.id,{'support_needs':'Updated synthetic support'},self.child.current_version)
        tick_response_policy(obj.id)
        self.assertFalse(Assignment.objects.exists())
        self.assertTrue(ResponseEscalation.objects.filter(kind='care_changed').exists())
        self.reviewed_plan(obj);tick_response_policy(obj.id)
        self.assertEqual(Assignment.objects.count(),1)
        self.assertEqual(ResponsePlanReview.objects.count(),2)

    def test_cross_region_candidates_and_unowned_plans_are_rejected(self):
        obj=self.accept()
        with self.assertRaises(Exception):configure_plan(self.coord,obj.id,True,[self.team.id],'Not owned')
        services.claim_ownership(self.coord,obj.id)
        remote=Team.objects.create(region=self.remote_region,name='Wrong area',available=True,on_duty=True)
        with self.assertRaisesMessage(Exception,'this incident region'):
            configure_plan(self.coord,obj.id,True,[remote.id],'Wrong region review')

    def test_expired_offer_notification_is_cancelled_before_processing(self):
        obj=self.accept();services.claim_ownership(self.coord,obj.id)
        offer=services.offer_team(self.coord,obj.id,self.team.id,True)
        offer.deadline=timezone.now()-timedelta(seconds=1);offer.save()
        process_notification_jobs()
        self.assertEqual(NotificationJob.objects.get(notification__audience='crew').status,'cancelled')

    def test_policy_api_requires_explicit_timings_and_on_call_people(self):
        body={'region':str(self.region.id),'enabled':True}
        response=self.as_user(self.admin).post('/api/v1/configuration/response-policies/',body,format='json')
        self.assertEqual(response.status_code,400,response.data)
        response=self.as_user(self.guardian).get('/api/v1/configuration/response-policies/')
        self.assertEqual(response.status_code,403)


@skipUnless(connection.vendor=='postgresql','Requires PostgreSQL row locking')
class ResponsePolicyConcurrencyTests(PolicySetup,TransactionTestCase):
    setUp=fixtures.FoundationTests.setUp
    accept=fixtures.FoundationTests.accept
    def test_parallel_policy_ticks_create_only_one_live_offer(self):
        obj=self.accept();self.policy();self.reviewed_plan(obj)
        barrier=Barrier(2)
        def run():
            try:
                barrier.wait(timeout=10);tick_response_policy(obj.id)
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(run) for _ in range(2)]
            for f in futures:f.result(timeout=20)
        self.assertEqual(Assignment.objects.count(),1)
        self.assertEqual(Notification.objects.filter(audience='crew').count(),1)
