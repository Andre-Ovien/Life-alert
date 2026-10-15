import uuid
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from incidents import tests as fixtures
from families.models import AuthorityRecord,CareMedia
from operations.models import Facility,FacilityStaff,CarePlace
from . import services,care
from .models import Placement,CareHandover,ResponseEscalation

class CareOperationsTests(TestCase):
    setUpBase=fixtures.FoundationTests.setUp
    accept=fixtures.FoundationTests.accept
    as_user=fixtures.FoundationTests.as_user
    def setUp(self):
        self.setUpBase();self.obj=self.accept();services.claim_ownership(self.coord,self.obj.id)
        self.facility=Facility.objects.create(region=self.region,name='Synthetic care facility',enabled=True,capacity=2,reservation_seconds=60)
        self.place=CarePlace.objects.create(facility=self.facility,label='Synthetic place one',enabled=True)
        self.proof=AuthorityRecord.objects.create(child=self.child,subject=self.guardian,purpose='placement',status='verified',
            evidence_reference='Synthetic placement authority',verification_reference='Operator assertion after external review',verified_by=self.coord,verified_at=timezone.now(),valid_until=timezone.now()+timedelta(days=1))
        self.release=AuthorityRecord.objects.create(child=self.child,subject=self.guardian,purpose='release',status='verified',
            evidence_reference='Synthetic release authority',verification_reference='Operator asserted recipient check',verified_by=self.coord,verified_at=timezone.now(),valid_until=timezone.now()+timedelta(days=1))
        FacilityStaff.objects.create(facility=self.facility,user=self.responder,active=True,on_duty=True,review_reference='Synthetic approved staff')
        FacilityStaff.objects.create(facility=self.facility,user=self.other,active=True,on_duty=True,review_reference='Synthetic approved incoming shift')
    def reserve(self):
        return services.reserve_placement(self.coord,self.obj.id,self.facility.id,self.proof.evidence_reference,True,self.proof.id,self.place.id)
    def intake(self):
        placement=self.reserve()
        handover=care.assign_staff(self.coord,placement.id,self.responder,'Intake handover')
        care.accept_staff_handover(self.responder,placement.id,handover.id)
        services.placement_transition(self.responder,self.obj.id,placement.id,'intake','Received verified handover',transport_reference='Approved transport reference',intake_reference='Intake evidence',belongings=['Synthetic item'])
        return placement

    def test_reservation_requires_current_reviewed_authority(self):
        self.proof.status='pending';self.proof.save()
        with self.assertRaisesMessage(Exception,'reviewed care authority'):self.reserve()
        self.assertFalse(Placement.objects.exists())

    def test_intake_requires_accepted_staff_and_transport_intake_evidence(self):
        placement=self.reserve()
        with self.assertRaisesMessage(Exception,'accept responsibility'):
            services.placement_transition(self.coord,self.obj.id,placement.id,'intake','No staff accepted')
        handover=care.assign_staff(self.coord,placement.id,self.responder,'Receive child')
        with self.assertRaises(Exception):care.accept_staff_handover(self.other,placement.id,handover.id)
        care.accept_staff_handover(self.responder,placement.id,handover.id)
        with self.assertRaisesMessage(Exception,'Transport and structured intake'):
            services.placement_transition(self.responder,self.obj.id,placement.id,'intake','Missing references')
        services.placement_transition(self.responder,self.obj.id,placement.id,'intake','Recorded intake',transport_reference='Approved transport',intake_reference='Verified intake')
        placement.refresh_from_db();self.assertEqual(placement.state,'intake')
        self.assertEqual(placement.current_staff_id,self.responder.id)

    def test_shift_handover_preserves_owner_until_receiving_staff_accepts(self):
        placement=self.intake();placement.refresh_from_db()
        handover=care.assign_staff(self.responder,placement.id,self.other,'Shift transition evidence')
        placement.refresh_from_db();self.assertEqual(placement.current_staff_id,self.responder.id)
        care.accept_staff_handover(self.other,placement.id,handover.id)
        placement.refresh_from_db();self.assertEqual(placement.current_staff_id,self.other.id)
        with self.assertRaises(Exception):care.record_care_event(self.responder,placement.id,uuid.uuid4(),'support','Former staff cannot write')
        event=care.record_care_event(self.other,placement.id,uuid.uuid4(),'support','Recorded individual support action')
        self.assertEqual(event.author_id,self.other.id)

    def test_release_requires_matching_current_authority_and_verified_recipient(self):
        placement=self.intake()
        with self.assertRaises(Exception):services.placement_transition(self.responder,self.obj.id,placement.id,'released','Contact alone is not authority',recipient=self.other,authority=self.release.id)
        services.placement_transition(self.responder,self.obj.id,placement.id,'released','Verified recipient handover reference',recipient=self.guardian,authority=self.release.id)
        placement.refresh_from_db();self.assertEqual(placement.state,'released')
        self.assertTrue(CareHandover.objects.filter(placement=placement,kind='release',recipient=self.guardian,status='accepted').exists())
        self.assertEqual(self.as_user(self.responder).get(f'/api/v1/placements/{placement.id}/').status_code,404)

    def test_expiry_only_cancels_unadmitted_reservation_and_keeps_escalation(self):
        placement=self.reserve();placement.reserved_until=timezone.now()-timedelta(seconds=1);placement.save()
        care.expire_reservations(self.obj.id);care.expire_reservations(self.obj.id)
        placement.refresh_from_db();self.assertEqual(placement.state,'cancelled')
        self.assertEqual(ResponseEscalation.objects.filter(kind='reservation_expired').count(),1)

    def test_capacity_failure_is_persistent_and_not_a_false_placement(self):
        self.facility.capacity=0;self.facility.save()
        with self.assertRaisesMessage(Exception,'No capacity'):self.reserve()
        self.assertFalse(Placement.objects.exists())
        self.assertEqual(ResponseEscalation.objects.get().kind,'care_capacity')

    def test_staff_can_read_only_assigned_care_and_instruction_media(self):
        placement=self.reserve()
        private=CareMedia.objects.create(child=self.child,title='Responder instruction',for_responder=True)
        self.assertEqual(self.as_user(self.responder).get(f'/api/v1/placements/{placement.id}/').status_code,404)
        handover=care.assign_staff(self.coord,placement.id,self.responder,'Care context for intake')
        result=self.client.get(f'/api/v1/placements/{placement.id}/')
        self.assertEqual(result.status_code,200,result.data)
        self.assertEqual(result.data['care']['name'],self.child.name)
        self.assertNotIn('places',result.data['care'])
        self.assertEqual(self.client.get(f'/api/v1/media/{private.id}/').status_code,200)
        self.assertEqual(self.as_user(self.guardian).get(f'/api/v1/placements/{placement.id}/').status_code,404)
        family=self.client.get(f'/api/v1/incidents/{self.obj.id}/care-placements/')
        self.assertEqual(family.status_code,200,family.data)
        self.assertNotIn('belongings',family.data['results'][0])

    def test_care_events_are_idempotent_and_cannot_change_under_same_key(self):
        placement=self.intake();key=uuid.uuid4()
        first=care.record_care_event(self.responder,placement.id,key,'observation','Synthetic observed preference')
        repeat=care.record_care_event(self.responder,placement.id,key,'observation','Synthetic observed preference')
        self.assertEqual(first.id,repeat.id)
        with self.assertRaisesMessage(Exception,'different data'):
            care.record_care_event(self.responder,placement.id,key,'observation','Modified record')

    def test_declined_care_handover_preserves_owner_and_can_be_replaced(self):
        placement=self.intake();placement.refresh_from_db()
        self.assertIsNotNone(placement.intake_at)
        handover=care.assign_staff(self.responder,placement.id,self.other,'Proposed shift')
        with self.assertRaises(Exception):care.end_staff_handover(self.guardian,placement.id,handover.id,'cancelled','Unauthorized')
        care.end_staff_handover(self.other,placement.id,handover.id,'declined','Incoming shift unavailable')
        placement.refresh_from_db();self.assertEqual(placement.current_staff_id,self.responder.id)
        self.assertFalse(placement.staff.filter(pk=self.other.pk).exists())
        self.assertTrue(placement.incident.escalations.filter(kind='care_handover').exists())
        replacement=care.assign_staff(self.responder,placement.id,self.other,'Revised shift arrangement')
        result=self.as_user(self.responder).post(f'/api/v1/placements/{placement.id}/handover-decision/',
            {'handover_id':str(replacement.id),'target':'cancelled','reference':'Current staff continues'},format='json')
        self.assertEqual(result.status_code,200,result.data)
        with self.assertRaises(Exception):care.accept_staff_handover(self.other,placement.id,replacement.id)
