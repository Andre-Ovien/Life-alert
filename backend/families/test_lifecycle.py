from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from django.test import TestCase,TransactionTestCase,override_settings
from django.db import connection,connections
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient
from incidents import tests as fixtures
from . import lifecycle
from .models import DeviceLinkChallenge,Device,Entitlement,BillingEvent

class LifecycleTests(TestCase):
    setUp=fixtures.FoundationTests.setUp
    as_user=fixtures.FoundationTests.as_user
    def event(self,event_id='one',revision=1,active=True):
        return lifecycle.apply_sandbox_billing_event(self.admin,self.household.id,event_id,revision,active,
            self.entitlement.starts_at,self.entitlement.ends_at)

    def test_pairing_is_one_use_and_does_not_require_child_adult_login(self):
        cache.clear()
        challenge,raw=lifecycle.start_pairing(self.guardian,self.child.id,'Synthetic paired device')
        client=APIClient()
        result=client.post('/api/v1/device-pairing/consume/',{'token':raw},format='json')
        self.assertEqual(result.status_code,201,result.data)
        self.assertNotIn('name',result.data)
        self.assertNotEqual(DeviceLinkChallenge.objects.get().digest,raw)
        client.credentials(HTTP_AUTHORIZATION='Device '+result.data['credential'])
        self.assertEqual(client.get('/api/v1/incidents/').status_code,200)
        with self.assertRaisesMessage(Exception,'used pairing'):
            lifecycle.consume_pairing(raw)

    def test_expired_revoked_and_revoked_creator_pairing_fails(self):
        challenge,raw=lifecycle.start_pairing(self.guardian,self.child.id,'Synthetic device')
        challenge.expires_at=timezone.now()-timedelta(seconds=1);challenge.save()
        with self.assertRaises(Exception):lifecycle.consume_pairing(raw)
        challenge,raw=lifecycle.start_pairing(self.guardian,self.child.id,'Synthetic device')
        lifecycle.revoke_pairing(self.guardian,challenge.id)
        with self.assertRaises(Exception):lifecycle.consume_pairing(raw)
        with self.assertRaises(Exception):lifecycle.start_pairing(self.other,self.child.id,'Unauthorized')

    def test_rotation_revokes_old_credential_and_preserves_child_scope(self):
        device,raw=lifecycle.rotate_device(self.guardian,self.device.id)
        self.device.refresh_from_db();self.assertIsNotNone(self.device.revoked_at)
        self.assertEqual(device.rotated_from_id,self.device.id)
        self.client.credentials(HTTP_AUTHORIZATION='Device '+self.token)
        self.assertEqual(self.client.get('/api/v1/incidents/').status_code,401)
        self.client.credentials(HTTP_AUTHORIZATION='Device '+raw)
        self.assertEqual(self.client.get('/api/v1/incidents/').status_code,200)
        with self.assertRaises(Exception):lifecycle.rotate_device(self.guardian,self.device.id)

    @override_settings(DEVICE_TOKEN_SECONDS=60)
    def test_configured_device_expiry_is_enforced_on_authentication(self):
        challenge,raw=lifecycle.start_pairing(self.guardian,self.child.id,'Expiring synthetic device')
        device,token=lifecycle.consume_pairing(raw)
        self.assertIsNotNone(device.expires_at)
        device.expires_at=timezone.now()-timedelta(seconds=1);device.save()
        self.client.credentials(HTTP_AUTHORIZATION='Device '+token)
        self.assertEqual(self.client.get('/api/v1/incidents/').status_code,401)

    def test_billing_duplicate_out_of_order_and_conflict_are_explicit(self):
        first=self.event(revision=2)
        again=self.event(revision=2)
        self.assertEqual(first.id,again.id)
        stale=self.event('stale',1,False)
        self.assertEqual(stale.status,'ignored')
        conflict=self.event('conflict',2,False)
        self.assertEqual(conflict.status,'conflict')
        self.entitlement.refresh_from_db();self.assertTrue(self.entitlement.active)
        with self.assertRaisesMessage(Exception,'different normalized data'):
            self.event('one',3,False)
        latest=self.event('new',3,False)
        self.assertEqual(latest.status,'applied')
        self.entitlement.refresh_from_db();self.assertFalse(self.entitlement.active)
        self.assertEqual(BillingEvent.objects.count(),4)

    def test_billing_ingestion_is_admin_only_and_never_real_processing(self):
        body={'household':str(self.household.id),'event_id':'synthetic-event','revision':1,'active':True,
            'starts_at':self.entitlement.starts_at.isoformat(),'ends_at':self.entitlement.ends_at.isoformat()}
        endpoint='/api/v1/configuration/billing-events/'
        self.assertEqual(self.as_user(self.guardian).post(endpoint,body,format='json').status_code,403)
        result=self.as_user(self.admin).post(endpoint,body,format='json')
        self.assertEqual(result.status_code,200,result.data)
        self.assertTrue(result.data['simulation'])
        self.assertEqual(result.data['status'],'applied')

    def test_readiness_reports_facts_without_a_service_guarantee(self):
        client=self.as_user(self.guardian)
        response=client.get(f'/api/v1/children/{self.child.id}/readiness/')
        self.assertEqual(response.status_code,200,response.data)
        self.assertFalse(response.data['guaranteed_service'])
        self.assertEqual(response.data['coverage'],'not_evaluated')
        self.assertEqual(response.data['required_care_fields'],'not_configured')
        entitlement=client.get(f'/api/v1/households/{self.household.id}/entitlement/')
        self.assertTrue(entitlement.data['active_entitlement'])
        self.assertTrue(entitlement.data['accepted_incidents_continue'])
        self.assertEqual(self.as_user(self.other).get(f'/api/v1/children/{self.child.id}/readiness/').status_code,404)


@skipUnless(connection.vendor=='postgresql','Requires PostgreSQL row locks')
class PairingConcurrencyTests(TransactionTestCase):
    setUp=fixtures.FoundationTests.setUp
    def test_one_use_challenge_cannot_issue_two_devices_in_parallel(self):
        challenge,raw=lifecycle.start_pairing(self.guardian,self.child.id,'Synthetic concurrency')
        barrier=Barrier(2)
        def run():
            try:
                barrier.wait(timeout=10)
                try:lifecycle.consume_pairing(raw);return 'consumed'
                except Exception as exc:
                    from rest_framework.exceptions import ValidationError
                    if not isinstance(exc,ValidationError):raise
                    return 'already_used'
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(run) for _ in range(2)]
            self.assertEqual({f.result(timeout=20) for f in futures},{'consumed','already_used'})
        self.assertEqual(Device.objects.filter(label='Synthetic concurrency').count(),1)
