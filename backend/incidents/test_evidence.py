import uuid
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from incidents import tests as fixtures
from operations.models import Coordinator
from . import services,evidence
from .models import LocationUpdate,EMSEvidenceEvent,Notification

class EvidenceTests(TestCase):
    setUp=fixtures.FoundationTests.setUp
    accept=fixtures.FoundationTests.accept
    as_user=fixtures.FoundationTests.as_user
    def test_location_updates_are_idempotent_reviewed_and_not_billed_as_new_help(self):
        obj=self.accept();key=uuid.uuid4()
        self.entitlement.ends_at=timezone.now()-timedelta(seconds=1);self.entitlement.save()
        report=evidence.report_location(self.actor,obj.id,key,{**self.location,'latitude':36})
        duplicate=evidence.report_location(self.actor,obj.id,key,{**self.location,'latitude':36})
        self.assertEqual(report.id,duplicate.id)
        obj.refresh_from_db();self.assertEqual(obj.location['latitude'],35)
        with self.assertRaises(Exception):evidence.review_location(self.guardian,obj.id,report.id,True,'Not a coordinator')
        evidence.review_location(self.coord,obj.id,report.id,True,'Confirmed current incident location')
        obj.refresh_from_db();self.assertEqual(obj.location['latitude'],36)
        self.assertEqual(obj.location_revision,1)
        self.assertEqual(LocationUpdate.objects.count(),1)

    def test_stale_location_remains_labeled_after_review_and_cannot_duplicate_payload(self):
        obj=self.accept();key=uuid.uuid4()
        stale={**self.location,'captured_at':timezone.now()-timedelta(hours=2)}
        report=evidence.report_location(self.guardian,obj.id,key,stale)
        self.assertEqual(report.quality,'stale')
        evidence.review_location(self.coord,obj.id,report.id,True,'Reviewed as stale evidence, not a live fix')
        obj.refresh_from_db();self.assertEqual(obj.location_quality,'stale')
        with self.assertRaisesMessage(Exception,'different data'):
            evidence.report_location(self.guardian,obj.id,key,self.location)

    def test_named_region_handover_requires_acceptance_and_restricts_new_scope(self):
        obj=self.accept();services.claim_ownership(self.coord,obj.id)
        target=Coordinator.objects.get(user=self.remote_coord,region=self.remote_region)
        target.on_duty=True;target.save();self.remote_region.enabled=True;self.remote_region.save()
        handover=evidence.request_handover(self.coord,obj.id,target.id,'Verified receiving duty responsibility')
        obj.refresh_from_db();self.assertEqual(obj.region_id,self.region.id)
        self.assertEqual(self.as_user(self.remote_coord).get(f'/api/v1/incidents/{obj.id}/').status_code,404)
        with self.assertRaises(Exception):evidence.accept_handover(self.guardian,handover.id)
        evidence.accept_handover(self.remote_coord,handover.id)
        obj.refresh_from_db();self.assertEqual(obj.region_id,self.remote_region.id)
        self.assertEqual(obj.coordinator_owner_id,self.remote_coord.id)
        self.assertEqual(self.as_user(self.coord).get(f'/api/v1/incidents/{obj.id}/').status_code,404)
        self.assertEqual(self.as_user(self.remote_coord).get(f'/api/v1/incidents/{obj.id}/').status_code,200)
        with self.assertRaises(Exception):evidence.accept_handover(self.remote_coord,handover.id)

    def test_reported_different_region_does_not_silently_transfer_responsibility(self):
        obj=self.accept();self.remote_region.enabled=True;self.remote_region.save()
        report=evidence.report_location(self.guardian,obj.id,uuid.uuid4(),{**self.location,'latitude':1.5,'longitude':1.5})
        evidence.review_location(self.coord,obj.id,report.id,True,'Operator reviewed reported move')
        obj.refresh_from_db()
        self.assertEqual(obj.region_id,self.region.id)
        self.assertTrue(obj.escalations.filter(kind='region_review').exists())

    def test_ems_evidence_replay_does_not_duplicate_or_regress_state(self):
        obj=self.accept();key=uuid.uuid4();at=timezone.now()
        services.record_ems(self.coord,obj.id,'contact_confirmed','Synthetic verified contact',key,at)
        services.record_ems(self.coord,obj.id,'dispatch_confirmed','Synthetic explicit dispatch evidence')
        current=services.record_ems(self.coord,obj.id,'contact_confirmed','Synthetic verified contact',key,at)
        self.assertEqual(current.state,'dispatch_confirmed')
        self.assertEqual(EMSEvidenceEvent.objects.count(),2)
        with self.assertRaisesMessage(Exception,'different data'):
            services.record_ems(self.coord,obj.id,'contact_confirmed','Changed evidence',key,at)
        with self.assertRaisesMessage(Exception,'Invalid EMS'):
            services.record_ems(self.coord,obj.id,'contact_confirmed','Late unsequenced event cannot regress dispatch')
        result=self.as_user(self.coord).get(f'/api/v1/incidents/{obj.id}/ems-events/')
        self.assertEqual(result.data['count'],2)

    def test_child_location_read_is_minimal_and_other_family_cannot_report(self):
        obj=self.accept()
        evidence.report_location(self.actor,obj.id,uuid.uuid4(),self.location)
        endpoint=f'/api/v1/incidents/{obj.id}/location-updates/'
        self.client.credentials(HTTP_AUTHORIZATION='Device '+self.token)
        result=self.client.get(endpoint)
        self.assertEqual(result.status_code,200,result.data)
        self.assertNotIn('location',result.data['results'][0])
        with self.assertRaises(Exception):evidence.report_location(self.other,obj.id,uuid.uuid4(),self.location)

    def test_declined_or_cancelled_region_handover_keeps_owner_and_allows_replacement(self):
        from .models import NotificationJob
        from .workflow import process_notification_jobs
        obj=self.accept();services.claim_ownership(self.coord,obj.id)
        target=Coordinator.objects.get(user=self.remote_coord,region=self.remote_region)
        target.on_duty=True;target.save();self.remote_region.enabled=True;self.remote_region.save()
        first=evidence.request_handover(self.coord,obj.id,target.id,'Synthetic receiving arrangement')
        with self.assertRaises(Exception):evidence.end_handover(self.guardian,first.id,'cancelled','Unauthorized')
        evidence.end_handover(self.remote_coord,first.id,'declined','Unavailable for this case')
        obj.refresh_from_db();self.assertEqual(obj.coordinator_owner_id,self.coord.id)
        self.assertTrue(obj.escalations.filter(kind='region_review').exists())
        second=evidence.request_handover(self.coord,obj.id,target.id,'Alternative reviewed arrangement')
        result=self.as_user(self.coord).post(f'/api/v1/region-handovers/{second.id}/decision/',
            {'target':'cancelled','reference':'Source retains responsibility'},format='json')
        self.assertEqual(result.status_code,200,result.data)
        process_notification_jobs()
        self.assertEqual(NotificationJob.objects.filter(notification__context_key__startswith='handover:',status='cancelled').count(),2)
        with self.assertRaises(Exception):evidence.accept_handover(self.remote_coord,second.id)

    def test_closure_cancels_unaccepted_regional_handover(self):
        obj=self.accept();services.claim_ownership(self.coord,obj.id)
        target=Coordinator.objects.get(user=self.remote_coord,region=self.remote_region)
        target.on_duty=True;target.save();self.remote_region.enabled=True;self.remote_region.save()
        handover=evidence.request_handover(self.coord,obj.id,target.id,'Pending receiving arrangement')
        services.transition(self.coord,obj.id,'cancelled',outcome='Reviewed before response started')
        handover.refresh_from_db();self.assertEqual(handover.status,'cancelled')
        with self.assertRaises(Exception):evidence.accept_handover(self.remote_coord,handover.id)
