import hashlib
import uuid
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from common.models import AuditEvent
from families.models import Household, Guardian, Child, Device, Entitlement, CareMedia
from families.authentication import DevicePrincipal
from operations.models import Region, Coordinator, Team, Facility
from .models import Incident, Assignment, Notification, Placement
from . import services

class FoundationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.guardian = User.objects.create_user('guardian')
        self.other = User.objects.create_user('other')
        self.coord = User.objects.create_user('coord')
        self.remote_coord = User.objects.create_user('remote')
        self.responder = User.objects.create_user('responder')
        self.admin = User.objects.create_superuser('admin', password='test-only-strong-passphrase')
        self.household = Household.objects.create(name='Synthetic family')
        Guardian.objects.create(household=self.household, user=self.guardian)
        self.child = Child.objects.create(household=self.household, name='Synthetic child', saved_address='Saved address - not live', support_needs='Individual support')
        self.sibling = Child.objects.create(household=self.household, name='Sibling')
        self.region = Region.objects.create(name='Synthetic region', enabled=True, min_lat=30, max_lat=40, min_lon=-80, max_lon=-70, ems_mode='simulated')
        self.remote_region = Region.objects.create(name='Remote', min_lat=1, max_lat=2, min_lon=1, max_lon=2)
        Coordinator.objects.create(user=self.coord, region=self.region)
        Coordinator.objects.create(user=self.remote_coord, region=self.remote_region)
        self.team = Team.objects.create(name='Synthetic crew', region=self.region, available=True, on_duty=True)
        self.team.members.add(self.responder)
        self.entitlement = Entitlement.objects.create(household=self.household, active=True, starts_at=timezone.now()-timedelta(days=1), ends_at=timezone.now()+timedelta(days=1))
        self.token = 'synthetic-test-device-token-only'
        self.device = Device.objects.create(child=self.child, label='Synthetic device', token_digest=hashlib.sha256(self.token.encode()).hexdigest())
        self.actor = DevicePrincipal(self.device)
        self.location = {'latitude':35.0,'longitude':-75.0,'accuracy_meters':20.0,'captured_at':timezone.now()}
        self.client = APIClient()

    def accept(self, key=None, location=None):
        return services.create_incident(self.actor, self.child.id, key or uuid.uuid4(), self.location if location is None else location)[0]

    def as_user(self, user):
        self.client.force_authenticate(user=user)
        return self.client

    def help_payload(self, child=None, key=None, location=None):
        loc = self.location if location is None else location
        return {'child':str((child or self.child).id),'request_id':str(key or uuid.uuid4()),'location':{**loc,'captured_at':loc['captured_at'].isoformat()} if loc else {}}

    def expire(self):
        self.entitlement.ends_at = timezone.now()-timedelta(seconds=1)
        self.entitlement.save()

    def triage(self, incident):
        return services.transition(self.coord, incident.id, 'triage')

    def test_linked_device_creates_without_parent_login_and_queues_parallel_work(self):
        self.client.credentials(HTTP_AUTHORIZATION='Device '+self.token)
        response = self.client.post('/api/v1/incidents/help/', self.help_payload(), format='json')
        self.assertEqual(response.status_code,201,response.data)
        self.assertEqual(set(response.data['incident']), {'id','state','review_required','cancellation_requested','receipt','emergency_call_separate','public_status'})
        obj = Incident.objects.get()
        self.assertEqual(set(obj.notifications.values_list('audience',flat=True)), {'guardian','coordinator'})
        self.assertEqual(obj.ems.state, 'handoff_pending')
        self.assertEqual(obj.state, 'received')

    def test_replay_after_expiry_does_not_create_or_repeat_jobs(self):
        key = uuid.uuid4()
        obj = self.accept(key)
        self.expire()
        replay,result = services.create_incident(self.actor,self.child.id,key,self.location)
        self.assertEqual(replay.id,obj.id)
        self.assertEqual(result,'replayed')
        self.assertEqual(Incident.objects.count(),1)
        self.assertEqual(Notification.objects.count(),2)
        with self.assertRaisesMessage(Exception,'active_subscription_required'):
            self.accept()

    def test_different_key_records_explicit_followup_review(self):
        obj=self.accept()
        result,meaning=services.create_incident(self.actor,self.child.id,uuid.uuid4(),self.location)
        self.assertEqual(result.id,obj.id)
        self.assertEqual(meaning,'followup_requires_review')
        obj.refresh_from_db()
        self.assertTrue(obj.review_required)
        self.assertTrue(AuditEvent.objects.filter(action='incident.followup_requires_review').exists())

    def test_changed_payload_with_same_key_is_rejected(self):
        key=uuid.uuid4(); self.accept(key)
        with self.assertRaisesMessage(Exception,'different location'):
            services.create_incident(self.actor,self.child.id,key,{**self.location,'latitude':36})

    def test_database_prevents_parallel_open_incidents(self):
        obj=self.accept()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Incident.objects.create(child=self.child, accepted_at=obj.accepted_at, accepted_entitlement_until=obj.accepted_entitlement_until, location_quality='missing')

    def test_expired_accepted_incident_continues_without_new_entitlement(self):
        obj=self.accept(); self.triage(obj); self.expire()
        active=services.transition(self.coord,obj.id,'active')
        self.assertEqual(active.state,'active')
        self.assertEqual(services.continuation_status(active),'continue_accepted_incident')
        with override_settings(CONTINUE_ACCEPTED_INCIDENTS=False):
            self.assertEqual(services.continuation_status(active),'policy_review_required')
        self.assertEqual(Entitlement.objects.get().active,True)

    def test_missing_and_stale_location_do_not_fabricate_live_address(self):
        obj=self.accept(location={})
        self.assertEqual(obj.location_quality,'missing'); self.assertIsNone(obj.region)
        self.assertIn('not live',obj.saved_address_fallback)
        obj.state='cancelled';obj.save()
        stale={**self.location,'captured_at':timezone.now()-timedelta(hours=2)}
        obj=self.accept(location=stale)
        self.assertEqual(obj.location_quality,'stale'); self.assertIsNone(obj.region)
        self.assertTrue(obj.review_required)

    def test_outside_coverage_does_not_cancel_subscription(self):
        with self.assertRaisesMessage(Exception,'outside_service_area'):
            self.accept(location={**self.location,'latitude':0})
        self.entitlement.refresh_from_db()
        self.assertTrue(self.entitlement.active)
        self.assertFalse(Incident.objects.exists())

    def test_cross_household_and_sibling_device_access_denied(self):
        obj=self.accept()
        response=self.as_user(self.other).get(f'/api/v1/incidents/{obj.id}/')
        self.assertEqual(response.status_code,404)
        self.assertEqual(self.client.get(f'/api/v1/children/{self.child.id}/').status_code,404)
        self.client.force_authenticate(user=None)
        self.client.credentials(HTTP_AUTHORIZATION='Device '+self.token)
        self.assertEqual(self.client.post('/api/v1/incidents/help/',self.help_payload(child=self.sibling),format='json').status_code,403)
        self.assertEqual(self.client.get('/api/v1/children/').status_code,403)

    def test_revoked_device_cannot_create_or_read(self):
        obj=self.accept()
        services.revoke_device(self.guardian,self.device.id)
        with self.assertRaisesMessage(Exception,'Device not authorized'):
            self.accept()
        self.client.credentials(HTTP_AUTHORIZATION='Device '+self.token)
        self.assertEqual(self.client.get(f'/api/v1/incidents/{obj.id}/').status_code,401)

    def test_guardian_cannot_change_lifecycle_and_other_region_cannot_read(self):
        obj=self.accept()
        with self.assertRaisesMessage(Exception,'Regional coordinator'):
            services.transition(self.guardian,obj.id,'triage')
        self.assertEqual(self.as_user(self.remote_coord).get(f'/api/v1/incidents/{obj.id}/').status_code,404)
        self.assertEqual(self.as_user(self.admin).get(f'/api/v1/incidents/{obj.id}/').status_code,404)

    def test_responder_access_only_after_acceptance_then_revoked_after_completion(self):
        obj=self.accept();self.triage(obj)
        offer=services.offer_team(self.coord,obj.id,self.team.id,True)
        self.assertEqual(self.as_user(self.responder).get(f'/api/v1/incidents/{obj.id}/care/').status_code,404)
        self.assertEqual(self.client.get('/api/v1/my-offers/').status_code,200)
        services.assignment_transition(self.responder,obj.id,offer.id,'accepted')
        self.assertEqual(self.client.get(f'/api/v1/incidents/{obj.id}/care/').status_code,200)
        for state in ['en_route','arrived','complete']:
            services.assignment_transition(self.responder,obj.id,offer.id,state)
        self.assertEqual(self.client.get(f'/api/v1/incidents/{obj.id}/care/').status_code,404)

    def test_no_acknowledgement_expires_offer_and_flags_review(self):
        obj=self.accept();self.triage(obj)
        offer=services.offer_team(self.coord,obj.id,self.team.id,True)
        offer.deadline=timezone.now()-timedelta(seconds=1);offer.save()
        services.process_simulated_work()
        offer.refresh_from_db();obj.refresh_from_db()
        self.assertEqual(offer.state,'timed_out');self.assertTrue(obj.review_required)
        self.assertEqual(obj.state,'triage')
        with self.assertRaises(Exception):
            services.assignment_transition(self.responder,obj.id,offer.id,'accepted')

    def test_invalid_state_transition_and_cancellation_review(self):
        obj=self.accept()
        with self.assertRaisesMessage(Exception,'Invalid lifecycle'):
            services.transition(self.coord,obj.id,'resolved',outcome='invalid')
        self.triage(obj)
        services.transition(self.coord,obj.id,'active')
        with self.assertRaises(Exception):
            services.transition(self.coord,obj.id,'cancelled',outcome='cancel',reconciled=True)
        services.request_cancellation(self.guardian,obj.id)
        services.record_ems(self.coord,obj.id,'closed','Coordinator verified no external action remains')
        cancelled=services.transition(self.coord,obj.id,'cancelled',outcome='Coordinator review complete',reconciled=True)
        self.assertEqual(cancelled.state,'cancelled')
        self.assertTrue(Incident.objects.filter(id=obj.id).exists())

    def test_simulated_provider_receipt_is_not_dispatch_and_is_idempotent(self):
        obj=self.accept()
        services.process_simulated_work();services.process_simulated_work()
        obj.ems.refresh_from_db()
        self.assertEqual(obj.ems.state,'provider_acknowledged')
        self.assertEqual(set(obj.notifications.values_list('state',flat=True)),{'simulated'})
        self.assertEqual(AuditEvent.objects.filter(action='ems.simulated').count(),1)
        with self.assertRaisesMessage(Exception,'Invalid EMS'):
            services.record_ems(self.coord,obj.id,'dispatch_confirmed','No contact evidence')
        services.record_ems(self.coord,obj.id,'contact_confirmed','Synthetic confirmed contact')
        services.record_ems(self.coord,obj.id,'dispatch_confirmed','Synthetic verified dispatch evidence')
        obj.refresh_from_db();self.assertEqual(obj.state,'received')

    @override_settings(SIMULATED_EMS_OUTCOME='timeout')
    def test_provider_timeout_stays_unknown_without_automatic_resubmission(self):
        obj=self.accept();services.process_simulated_work();services.process_simulated_work()
        obj.ems.refresh_from_db()
        self.assertEqual(obj.ems.state,'unknown')
        self.assertEqual(AuditEvent.objects.filter(action='ems.simulated').count(),1)

    def test_capacity_and_release_authority_boundary(self):
        obj=self.accept();self.triage(obj)
        facility=Facility.objects.create(region=self.region,name='Synthetic facility',enabled=True,capacity=1)
        with self.assertRaisesMessage(Exception,'verified authority'):
            services.reserve_placement(self.coord,obj.id,facility.id,'',True)
        place=services.reserve_placement(self.coord,obj.id,facility.id,'verified-authority-reference',True)
        other=services.create_incident(self.guardian,self.sibling.id,uuid.uuid4(),self.location)[0]
        self.triage(other)
        with self.assertRaisesMessage(Exception,'No capacity'):
            services.reserve_placement(self.coord,other.id,facility.id,'authority-ref',True)
        services.placement_transition(self.coord,obj.id,place.id,'intake','verified-intake-handover')
        with self.assertRaisesMessage(Exception,'Regional coordinator'):
            services.placement_transition(self.guardian,obj.id,place.id,'released','contact-is-not-release-authority')
        services.placement_transition(self.coord,obj.id,place.id,'released','verified-recipient-and-authority')
        self.assertEqual(Placement.objects.get(pk=place.id).state,'released')

    def test_media_purpose_and_family_boundaries(self):
        comfort=CareMedia.objects.create(child=self.child,title='Comfort',for_child=True)
        private=CareMedia.objects.create(child=self.child,title='Responder only',for_responder=True,instructions_text='Private care instructions')
        self.client.credentials(HTTP_AUTHORIZATION='Device '+self.token)
        data=self.client.get('/api/v1/media/').data
        self.assertEqual([x['id'] for x in data['results']],[str(comfort.id)])
        self.assertEqual(self.client.get(f'/api/v1/media/{private.id}/').status_code,404)
        self.assertEqual(self.as_user(self.other).get(f'/api/v1/media/{comfort.id}/').status_code,404)

    def test_audited_configuration_and_entitlement_renewal(self):
        self.assertEqual(self.as_user(self.guardian).get('/api/v1/configuration/regions/').status_code,403)
        data={'household':str(self.household.id),'active':True,'starts_at':(timezone.now()-timedelta(days=1)).isoformat(),'ends_at':(timezone.now()+timedelta(days=3)).isoformat()}
        response=self.as_user(self.admin).post('/api/v1/configuration/entitlements/',data,format='json')
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(Entitlement.objects.count(),1)
        self.assertTrue(AuditEvent.objects.filter(action='entitlement.configured').exists())

    def test_unknown_location_requires_audited_regional_assignment(self):
        obj=self.accept(location={})
        self.assertEqual(self.as_user(self.coord).get(f'/api/v1/incidents/{obj.id}/').status_code,404)
        response=self.as_user(self.admin).post(f'/api/v1/configuration/unrouted/{obj.id}/route/',{'region':str(self.region.id),'location_verified':True},format='json')
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(self.as_user(self.coord).get(f'/api/v1/incidents/{obj.id}/').status_code,200)

    def test_malformed_and_nonfinite_locations_do_not_create_incident(self):
        client=self.as_user(self.guardian)
        data=self.help_payload();data['location']['latitude']='NaN'
        self.assertEqual(client.post('/api/v1/incidents/help/',data,format='json').status_code,400)
        self.assertFalse(Incident.objects.exists())

    def test_registration_and_login_require_csrf(self):
        client=APIClient(enforce_csrf_checks=True)
        self.assertEqual(client.post('/api/v1/register/',{'username':'new','password':'LongTestPhrase847!','household_name':'New'},format='json').status_code,403)
        csrf=client.get('/api/v1/session/').data['csrf_token']
        response=client.post('/api/v1/register/',{'username':'new','password':'LongTestPhrase847!','household_name':'New'},format='json',HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(response.status_code,201,response.data)
        self.assertFalse(Entitlement.objects.filter(household_id=response.data['household']).exists())
        response=client.post('/api/v1/session/',{'username':'new','password':'LongTestPhrase847!'},format='json',HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(client.get('/api/v1/households/').status_code,200)

    def test_api_has_no_public_media_url_and_sensitive_responses_not_cached(self):
        response=self.as_user(self.guardian).get(f'/api/v1/children/{self.child.id}/')
        self.assertEqual(response['Cache-Control'],'private, no-store')
        self.assertTrue(AuditEvent.objects.filter(action='child.read').exists())
        self.assertEqual(self.client.get('/media/care/example.wav').status_code,404)

    def test_decline_requires_reason_and_flags_coordinator_review(self):
        obj=self.accept();self.triage(obj)
        offer=services.offer_team(self.coord,obj.id,self.team.id,True)
        with self.assertRaisesMessage(Exception,'decline reason'):
            services.assignment_transition(self.responder,obj.id,offer.id,'declined')
        declined=services.assignment_transition(self.responder,obj.id,offer.id,'declined','Vehicle unavailable')
        self.assertEqual(declined.decline_reason,'Vehicle unavailable')
        obj.refresh_from_db();self.assertTrue(obj.review_required)

    def test_off_duty_team_is_not_offered(self):
        obj=self.accept();self.triage(obj)
        self.team.on_duty=False;self.team.save()
        with self.assertRaisesMessage(Exception,'Available regional team'):
            services.offer_team(self.coord,obj.id,self.team.id,True)

    def test_api_missing_location_is_accepted_as_unknown(self):
        data=self.help_payload();data.pop('location')
        response=self.as_user(self.guardian).post('/api/v1/incidents/help/',data,format='json')
        self.assertEqual(response.status_code,201,response.data)
        self.assertEqual(response.data['incident']['location_quality'],'missing')

    def test_second_live_offer_is_rejected(self):
        obj=self.accept();self.triage(obj)
        services.offer_team(self.coord,obj.id,self.team.id,True)
        with self.assertRaisesMessage(Exception,'already exists'):
            services.offer_team(self.coord,obj.id,self.team.id,True)

    def test_coordinator_owns_solution_and_documents_progress(self):
        obj=self.accept()
        with self.assertRaisesMessage(Exception,'acknowledged coordinator owner'):
            services.record_progress(self.coord,obj.id,'Contact attempt','Arrange appropriate response')
        claimed=services.claim_ownership(self.coord,obj.id)
        self.assertEqual(claimed.coordinator_owner_id,self.coord.id)
        self.assertEqual(claimed.state,'triage')
        Coordinator.objects.create(user=self.remote_coord,region=self.region)
        with self.assertRaisesMessage(Exception,'takeover reason'):
            services.claim_ownership(self.remote_coord,obj.id)
        services.claim_ownership(self.remote_coord,obj.id,'Regional shift handover verified')
        services.claim_ownership(self.coord,obj.id,'Original coordinator resumes ownership')
        self.assertTrue(obj.progress_notes.filter(action_taken__contains='Regional shift handover').exists())
        note=services.record_progress(self.coord,obj.id,'Contacted authorized caregiver','Verify handover before resolution')
        self.assertEqual(note.author_id,self.coord.id)
        self.assertTrue(AuditEvent.objects.filter(action='incident.progress_recorded').exists())
        services.transition(self.coord,obj.id,'active')
        with self.assertRaisesMessage(Exception,'reconciled'):
            services.transition(self.coord,obj.id,'resolved',outcome='No accommodation needed')
        services.record_ems(self.coord,obj.id,'closed','Verified EMS disposition, no outstanding external response')
        resolved=services.transition(self.coord,obj.id,'resolved',outcome='Assistance provided, authorized caregiver handover verified, follow-up assigned',reconciled=True)
        self.assertEqual(resolved.state,'resolved')


    def test_notification_acknowledgement_is_separate_from_delivery_and_ownership(self):
        obj=self.accept()
        notification=services.acknowledge_notification(self.guardian,obj.id,'guardian')
        self.assertEqual(notification.state,'queued')
        self.assertIsNotNone(notification.acknowledged_at)
        services.acknowledge_notification(self.coord,obj.id,'coordinator')
        obj.refresh_from_db()
        self.assertIsNone(obj.coordinator_owner)
        self.assertEqual(obj.state,'received')
        services.process_simulated_work()
        notification.refresh_from_db()
        self.assertEqual(notification.state,'simulated')
        self.assertIsNotNone(notification.acknowledged_at)
        with self.assertRaisesMessage(Exception,'Regional coordinator'):
            services.acknowledge_notification(self.guardian,obj.id,'coordinator')

    def test_reassurance_is_based_on_actual_team_evidence(self):
        obj=self.accept()
        self.assertEqual(services.public_status(obj)['code'],'request_received')
        services.process_simulated_work()
        self.assertEqual(services.public_status(obj)['code'],'request_received')
        obj=self.triage(obj)
        self.assertEqual(services.public_status(obj)['code'],'coordinator_review')
        offer=services.offer_team(self.coord,obj.id,self.team.id,True)
        self.assertEqual(services.public_status(obj)['code'],'contacting_response_team')
        services.assignment_transition(self.responder,obj.id,offer.id,'accepted')
        self.assertEqual(services.public_status(obj)['code'],'team_assigned')
        services.assignment_transition(self.responder,obj.id,offer.id,'en_route')
        self.assertEqual(services.public_status(obj)['code'],'team_en_route')
        self.assertIn('on the way',services.public_status(obj)['message'])


from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from django.db import connection, connections
from django.test import TransactionTestCase

@skipUnless(connection.vendor == 'postgresql', 'Requires PostgreSQL row locking; SQLite is smoke-test only')
class PostgreSQLConcurrencyTests(TransactionTestCase):
    setUp = FoundationTests.setUp

    def run_requests(self, keys):
        barrier=Barrier(2)
        def work(key):
            try:
                actor=DevicePrincipal(Device.objects.get(pk=self.device.id))
                barrier.wait(timeout=10)
                incident,result=services.create_incident(actor,self.child.id,key,self.location)
                return str(incident.id),result
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(work,key) for key in keys]
            return [f.result(timeout=20) for f in futures]

    def test_same_request_parallel_taps_are_idempotent(self):
        key=uuid.uuid4()
        results=self.run_requests([key,key])
        self.assertEqual(len({x[0] for x in results}),1)
        self.assertEqual({x[1] for x in results},{'accepted','replayed'})
        self.assertEqual(Incident.objects.count(),1)
        self.assertEqual(Notification.objects.count(),2)

    def test_distinct_requests_serialize_and_record_followup(self):
        results=self.run_requests([uuid.uuid4(),uuid.uuid4()])
        self.assertEqual(len({x[0] for x in results}),1)
        self.assertEqual({x[1] for x in results},{'accepted','followup_requires_review'})
        self.assertTrue(Incident.objects.get().review_required)

    def test_entitlement_expiry_serializes_before_new_acceptance(self):
        from threading import Event
        started=Event()
        def work():
            try:
                actor=DevicePrincipal(Device.objects.get(pk=self.device.id))
                started.set()
                try:
                    services.create_incident(actor,self.child.id,uuid.uuid4(),self.location)
                    return 'accepted'
                except Exception as exc:
                    from rest_framework.exceptions import ValidationError
                    if not isinstance(exc,ValidationError):
                        raise
                    return 'not_entitled'
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic():
                Household.objects.select_for_update().get(pk=self.household.id)
                future=pool.submit(work)
                self.assertTrue(started.wait(timeout=10))
                self.entitlement.ends_at=timezone.now()-timedelta(seconds=1)
                self.entitlement.save()
            self.assertEqual(future.result(timeout=20),'not_entitled')
        self.assertFalse(Incident.objects.exists())

    def test_capacity_reservations_are_atomic_across_incidents(self):
        incidents=[]
        for child in [self.child,self.sibling]:
            obj=services.create_incident(self.guardian,child.id,uuid.uuid4(),self.location)[0]
            services.transition(self.coord,obj.id,'triage')
            incidents.append(obj)
        facility=Facility.objects.create(region=self.region,name='One place',capacity=1,enabled=True)
        barrier=Barrier(2)
        def work(obj):
            try:
                barrier.wait(timeout=10)
                try:
                    services.reserve_placement(self.coord,obj.id,facility.id,'synthetic-authority',True)
                    return 'reserved'
                except Exception as exc:
                    from rest_framework.exceptions import ValidationError
                    if not isinstance(exc,ValidationError):
                        raise
                    return 'capacity_unavailable'
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(work,obj) for obj in incidents]
            results=[f.result(timeout=20) for f in futures]
        self.assertEqual(set(results),{'reserved','capacity_unavailable'})
        self.assertEqual(Placement.objects.count(),1)


class MediaStreamingTests(TransactionTestCase):
    # Streaming response closure ends request DB connections; exercise outside
    # TestCase's wrapping transaction to match actual request lifecycles.
    setUp = FoundationTests.setUp
    as_user = FoundationTests.as_user

    def test_media_audio_upload_and_audience_permission_change(self):
        import io, wave, tempfile
        from django.core.files.uploadedfile import SimpleUploadedFile
        obj=CareMedia.objects.create(child=self.child,title='Comfort',for_child=True)
        buffer=io.BytesIO()
        with wave.open(buffer,'wb') as audio:
            audio.setnchannels(1);audio.setsampwidth(2);audio.setframerate(8000);audio.writeframes(b'\x00\x00'*800)
        with tempfile.TemporaryDirectory() as root, override_settings(MEDIA_ROOT=root):
            response=self.as_user(self.guardian).post(f'/api/v1/media/{obj.id}/upload/',{'audio':SimpleUploadedFile('sample.wav',buffer.getvalue(),content_type='audio/wav')},format='multipart')
            self.assertEqual(response.status_code,200,response.data)
            self.assertNotIn('file',response.data)
            self.client.force_authenticate(user=None);self.client.credentials(HTTP_AUTHORIZATION='Device '+self.token)
            response=self.client.get(f'/api/v1/media/{obj.id}/audio/')
            self.assertEqual(response.status_code,200);response.close()
            self.as_user(self.guardian).patch(f'/api/v1/media/{obj.id}/',{'for_child':False,'for_responder':True},format='json')
            self.client.force_authenticate(user=None);self.client.credentials(HTTP_AUTHORIZATION='Device '+self.token)
            self.assertEqual(self.client.get(f'/api/v1/media/{obj.id}/audio/').status_code,404)
