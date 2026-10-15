import uuid
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from django.db import connection,connections
from django.test import TestCase,TransactionTestCase
from django.utils import timezone
from incidents import tests as fixtures
from incidents import services as incidents
from . import services
from .models import CaregiverGrant,AuthorityRecord,CareVersion,SavedPlace

class FamilyCareTests(TestCase):
    setUp=fixtures.FoundationTests.setUp
    accept=fixtures.FoundationTests.accept
    as_user=fixtures.FoundationTests.as_user

    def test_direct_contact_reads_are_scoped_and_structurally_audited(self):
        from .models import EmergencyContact
        from common.models import AuditEvent
        contact=EmergencyContact.objects.create(child=self.child,name='Synthetic contact',phone='test-only',relationship='Caregiver')
        self.assertEqual(self.as_user(self.other).get(f'/api/v1/contacts/{contact.id}/').status_code,404)
        self.assertEqual(self.as_user(self.guardian).get(f'/api/v1/contacts/{contact.id}/').status_code,200)
        event=AuditEvent.objects.get(action='family.resource_read',object_id=contact.id)
        self.assertEqual(event.facts,{'model':'families.EmergencyContact'})
        self.assertNotIn('test-only',str(event.facts))

    def invite(self,permissions=None):
        return services.invite_caregiver(self.guardian,self.child.id,self.other,'Authorized caregiver',permissions or ['view_care'])

    def test_invite_requires_recipient_and_does_not_create_care_authority(self):
        invite,token=self.invite()
        with self.assertRaisesMessage(Exception,'another account'):
            services.accept_invitation(self.coord,token)
        services.accept_invitation(self.other,token)
        grant=CaregiverGrant.objects.get()
        self.assertTrue(grant.can_view_care)
        self.assertFalse(grant.can_request_help)
        self.assertFalse(AuthorityRecord.objects.exists())
        with self.assertRaisesMessage(Exception,'already used'):
            services.accept_invitation(self.other,token)

    def test_expired_or_revoked_invite_cannot_grant_access(self):
        invite,token=self.invite()
        invite.expires_at=timezone.now()-timedelta(seconds=1);invite.save()
        with self.assertRaises(Exception):services.accept_invitation(self.other,token)
        invite,token=self.invite();invite.status='revoked';invite.save()
        with self.assertRaises(Exception):services.accept_invitation(self.other,token)
        self.assertFalse(CaregiverGrant.objects.exists())

    def test_explicit_read_grant_does_not_allow_profile_or_device_mutation(self):
        invite,token=self.invite();services.accept_invitation(self.other,token)
        client=self.as_user(self.other)
        self.assertEqual(client.get(f'/api/v1/children/{self.child.id}/').status_code,200)
        self.assertEqual(client.get(f'/api/v1/children/{self.sibling.id}/').status_code,404)
        response=client.patch(f'/api/v1/children/{self.child.id}/',{'communication':'not permitted','expected_version':0},format='json')
        self.assertEqual(response.status_code,403)
        response=client.post('/api/v1/devices/',{'child':str(self.child.id),'label':'not permitted'},format='json')
        self.assertEqual(response.status_code,403)

    def test_grant_revocation_removes_profile_and_incident_access(self):
        invite,token=self.invite(['view_care','view_incidents','request_help'])
        services.accept_invitation(self.other,token)
        obj=incidents.create_incident(self.other,self.child.id,uuid.uuid4(),self.location)[0]
        self.assertEqual(self.as_user(self.other).get(f'/api/v1/incidents/{obj.id}/').status_code,200)
        services.revoke_grant(self.guardian,CaregiverGrant.objects.get().id)
        self.assertEqual(self.client.get(f'/api/v1/children/{self.child.id}/').status_code,404)
        self.assertEqual(self.client.get(f'/api/v1/incidents/{obj.id}/').status_code,404)
        with self.assertRaises(Exception):incidents.create_incident(self.other,self.child.id,uuid.uuid4(),self.location)

    def test_profile_update_conflicts_and_incident_care_snapshot_is_immutable(self):
        child=services.update_profile(self.guardian,self.child.id,{'communication':'Original preference'},0)
        obj=self.accept()
        with self.assertRaisesMessage(Exception,'Profile changed'):
            services.update_profile(self.guardian,self.child.id,{'communication':'Stale overwrite'},0)
        services.update_profile(self.guardian,self.child.id,{'communication':'New preference'},child.current_version)
        obj.refresh_from_db()
        self.assertEqual(obj.care_version.payload['communication'],'Original preference')
        response=self.as_user(self.coord).get(f'/api/v1/incidents/{obj.id}/care/')
        self.assertEqual(response.status_code,200,response.data)
        self.assertFalse(response.data['snapshot_is_current'])
        self.assertEqual(response.data['communication'],'Original preference')
        self.assertEqual(CareVersion.objects.filter(child=self.child).count(),2)

    def test_child_profile_api_requires_expected_version(self):
        response=self.as_user(self.guardian).patch(f'/api/v1/children/{self.child.id}/',{'communication':'Update'},format='json')
        self.assertEqual(response.status_code,400)
        response=self.client.patch(f'/api/v1/children/{self.child.id}/',{'communication':'Update','expected_version':0},format='json')
        self.assertEqual(response.status_code,200,response.data)
        self.assertEqual(response.data['current_version'],1)
        self.assertNotIn('expected_version',response.data)
        response=self.client.get(f'/api/v1/children/{self.child.id}/versions/')
        self.assertEqual(response.data['count'],1)

    def test_saved_default_places_update_fallback_and_version(self):
        first=services.save_place(self.guardian,self.child.id,{'label':'One','address':'Synthetic address one','is_default':True})
        second=services.save_place(self.guardian,self.child.id,{'label':'Two','address':'Synthetic address two','is_default':True})
        self.assertEqual(SavedPlace.objects.filter(child=self.child,is_default=True,active=True).count(),1)
        self.child.refresh_from_db();self.assertEqual(self.child.saved_address,'Synthetic address two')
        obj=incidents.create_incident(self.actor,self.child.id,uuid.uuid4(),{})[0]
        self.assertEqual(obj.saved_address_fallback,'Synthetic address two')
        self.assertEqual(obj.location_quality,'missing')
        self.assertEqual(len(obj.care_version.payload['places']),2)
        first.refresh_from_db();self.assertFalse(first.is_default)
        self.assertEqual(second.child_id,self.child.id)

    def test_contact_updates_capture_version_and_never_confer_authority(self):
        client=self.as_user(self.guardian)
        result=client.post('/api/v1/contacts/',{'child':str(self.child.id),'name':'Synthetic contact','phone':'5550100','relationship':'Contact'},format='json')
        self.assertEqual(result.status_code,201,result.data)
        result=client.patch(f"/api/v1/contacts/{result.data['id']}/",{'active':False},format='json')
        self.assertEqual(result.status_code,200,result.data)
        self.child.refresh_from_db();self.assertEqual(self.child.current_version,2)
        self.assertEqual(self.child.care_versions.get(number=2).payload['contacts'],[])
        self.assertFalse(AuthorityRecord.objects.exists())

    def test_authority_record_requires_regional_operator_review(self):
        obj=self.accept()
        client=self.as_user(self.guardian)
        result=client.post('/api/v1/authorities/',{'child':str(self.child.id),'subject':self.other.id,'purpose':'release',
            'evidence_reference':'Synthetic external evidence','valid_until':(timezone.now()+timedelta(days=1)).isoformat()},format='json')
        self.assertEqual(result.status_code,201,result.data)
        authority_id=result.data['id'];self.assertEqual(result.data['status'],'pending')
        body={'incident':str(obj.id),'status':'verified','verification_reference':'Operator assertion after external process'}
        endpoint=f'/api/v1/authorities/{authority_id}/review/'
        self.assertEqual(client.post(endpoint,body,format='json').status_code,403)
        self.assertEqual(self.as_user(self.remote_coord).post(endpoint,body,format='json').status_code,403)
        result=self.as_user(self.coord).post(endpoint,body,format='json')
        self.assertEqual(result.status_code,200,result.data)
        self.assertEqual(result.data['status'],'verified')
        self.assertFalse(CaregiverGrant.objects.exists())

    def test_invitation_api_returns_token_only_once_and_sends_nothing(self):
        result=self.as_user(self.guardian).post('/api/v1/caregiver-invitations/',{'child':str(self.child.id),'recipient':self.other.id,
            'relationship':'Synthetic caregiver','permissions':['view_care']},format='json')
        self.assertEqual(result.status_code,201,result.data)
        self.assertEqual(result.data['delivery'],'manual_sandbox_only')
        read=self.client.get(f"/api/v1/caregiver-invitations/{result.data['id']}/")
        self.assertNotIn('invitation_token',read.data)
        accepted=self.as_user(self.other).post('/api/v1/caregiver-invitations/consume/',{'token':result.data['invitation_token']},format='json')
        self.assertEqual(accepted.status_code,200,accepted.data)


@skipUnless(connection.vendor=='postgresql','Requires PostgreSQL row locking')
class CareConcurrencyTests(TransactionTestCase):
    setUp=fixtures.FoundationTests.setUp
    def test_concurrent_profile_edits_cannot_overwrite_same_version(self):
        barrier=Barrier(2)
        def run(value):
            try:
                barrier.wait(timeout=10)
                try:
                    services.update_profile(self.guardian,self.child.id,{'communication':value},0)
                    return 'saved'
                except Exception as exc:
                    from rest_framework.exceptions import ValidationError
                    if not isinstance(exc,ValidationError):raise
                    return 'conflict'
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures=[pool.submit(run,value) for value in ['one','two']]
            self.assertEqual({f.result(timeout=20) for f in futures},{'saved','conflict'})
        self.assertEqual(CareVersion.objects.count(),1)
