import io,tempfile,uuid,wave
from datetime import timedelta
from django.test import TransactionTestCase,override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from incidents import tests as fixtures
from families.models import CareMedia,RetiredMediaBlob
from .models import RetentionPolicy,PrivacyDecision
from . import privacy

class PrivacyTests(TransactionTestCase):
    setUpBase=fixtures.FoundationTests.setUp
    as_user=fixtures.FoundationTests.as_user
    def setUp(self):
        self.setUpBase();self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.override=override_settings(MEDIA_ROOT=self.temp.name);self.override.enable();self.addCleanup(self.override.disable)
        self.media=CareMedia.objects.create(child=self.child,title='Synthetic comfort',for_child=True)
    def wav(self):
        buffer=io.BytesIO()
        with wave.open(buffer,'wb') as f:
            f.setnchannels(1);f.setsampwidth(2);f.setframerate(8000);f.writeframes(b'\x00\x00'*800)
        return buffer.getvalue()
    def upload(self,data=None):
        result=self.as_user(self.guardian).post(f'/api/v1/media/{self.media.id}/upload/',{'audio':SimpleUploadedFile('synthetic.wav',self.wav() if data is None else data,content_type='audio/wav')},format='multipart')
        self.assertEqual(result.status_code,200,result.data)
        self.media.refresh_from_db();return self.media.file.name
    def request(self,kind='media_delete'):
        return privacy.submit_request(self.guardian,uuid.uuid4(),kind,child_id=self.child.id,media_id=self.media.id if kind=='media_delete' else None)
    def policy(self):return RetentionPolicy.objects.create(purpose='media',enabled=True,minimum_seconds=0,review_reference='Synthetic reviewed retention policy')

    def test_unknown_retention_and_legal_hold_fail_closed(self):
        name=self.upload();case=self.request()
        result=privacy.review_request(self.admin,case.id,'approved','Reviewed deletion request')
        self.assertEqual(result.status,'hold');self.assertIsNone(self.media.archived_at)
        self.assertEqual(privacy.purge_media_due(),0)
        self.assertTrue(self.media.file.storage.exists(name))
        self.policy();self.media.legal_hold=True;self.media.save()
        result=privacy.review_request(self.admin,case.id,'approved','Held media cannot be purged')
        self.assertEqual(result.status,'hold')
        self.assertEqual(PrivacyDecision.objects.filter(request=case).count(),2)

    def test_reviewed_archive_denies_access_and_purge_removes_all_versions(self):
        old=self.upload();new=self.upload()
        self.assertEqual(RetiredMediaBlob.objects.count(),1)
        case=self.request();self.policy()
        result=privacy.review_request(self.admin,case.id,'approved','Verified subject request under configured policy')
        self.assertEqual(result.status,'processing')
        self.client.force_authenticate(user=None);self.client.credentials(HTTP_AUTHORIZATION='Device '+self.token)
        self.assertEqual(self.client.get(f'/api/v1/media/{self.media.id}/audio/').status_code,404)
        self.assertEqual(privacy.purge_media_due(timezone.now()+timedelta(seconds=1)),1)
        self.assertFalse(self.media.file.storage.exists(old));self.assertFalse(self.media.file.storage.exists(new))
        self.assertEqual(privacy.purge_media_due(timezone.now()+timedelta(days=1)),0)

    def test_hold_added_after_approval_stops_purge(self):
        name=self.upload();case=self.request();self.policy()
        privacy.review_request(self.admin,case.id,'approved','Approved before hold')
        self.media.refresh_from_db();self.media.legal_hold=True;self.media.save()
        self.assertEqual(privacy.purge_media_due(timezone.now()+timedelta(days=1)),0)
        self.assertTrue(self.media.file.storage.exists(name))

    def test_request_id_reuse_and_cross_family_scope_are_guarded(self):
        key=uuid.uuid4()
        one=privacy.submit_request(self.guardian,key,'export',child_id=self.child.id)
        two=privacy.submit_request(self.guardian,key,'export',child_id=self.child.id)
        self.assertEqual(one.id,two.id)
        with self.assertRaises(Exception):privacy.submit_request(self.guardian,key,'correction',child_id=self.child.id)
        with self.assertRaises(Exception):privacy.submit_request(self.other,uuid.uuid4(),'export',child_id=self.child.id)
        with self.assertRaises(Exception):privacy.review_request(self.guardian,one.id,'approved','Cannot self approve')

    def test_export_is_approved_and_requester_only_without_credentials_or_audio(self):
        self.upload();case=self.request('export')
        with self.assertRaises(Exception):privacy.prepare_export(self.guardian,case.id)
        privacy.review_request(self.admin,case.id,'approved','Verified export scope')
        with self.assertRaises(Exception):privacy.prepare_export(self.other,case.id)
        data=privacy.prepare_export(self.guardian,case.id)
        self.assertEqual(data['child']['name'],self.child.name)
        self.assertFalse(data['audio_included'])
        self.assertNotIn('password',data['account'])
        self.assertNotIn('storage_name',str(data))

    def test_account_closure_holds_for_active_care_or_last_guardian(self):
        case=privacy.submit_request(self.guardian,uuid.uuid4(),'account_close')
        result=privacy.review_request(self.admin,case.id,'approved','Account closure reviewed')
        self.assertEqual(result.status,'hold')
        self.guardian.refresh_from_db();self.assertTrue(self.guardian.is_active)

    def test_correction_applies_a_new_care_version_after_review(self):
        case=self.request('correction')
        with self.assertRaises(Exception):privacy.apply_correction(self.guardian,case.id,0,{'communication':'Updated'})
        privacy.review_request(self.admin,case.id,'approved','Approved subject correction')
        result=privacy.apply_correction(self.guardian,case.id,0,{'communication':'Corrected synthetic preference'})
        self.assertEqual(result.status,'fulfilled')
        self.child.refresh_from_db();self.assertEqual(self.child.current_version,1)

    def test_truncated_audio_cannot_bypass_upload_validation(self):
        result=self.as_user(self.guardian).post(f'/api/v1/media/{self.media.id}/upload/',
            {'audio':SimpleUploadedFile('truncated.wav',self.wav()[:50],content_type='audio/wav')},format='multipart')
        self.assertEqual(result.status_code,400)
        self.media.refresh_from_db();self.assertFalse(self.media.file)

    def test_reviewed_account_close_revokes_adult_sessions_and_preserves_child_device(self):
        from families.models import Guardian
        from .identity import issue_tokens
        from .models import AdultTokenSession
        Guardian.objects.create(user=self.other,household=self.household)
        self.guardian.set_password('Synthetic-Closure-Password-463!');self.guardian.save()
        issue_tokens(self.guardian.username,'Synthetic-Closure-Password-463!')
        case=privacy.submit_request(self.guardian,uuid.uuid4(),'account_close')
        result=privacy.review_request(self.admin,case.id,'approved','Verified adult closure with remaining guardian')
        self.assertEqual(result.status,'fulfilled')
        self.guardian.refresh_from_db();self.assertFalse(self.guardian.is_active)
        self.assertIsNotNone(AdultTokenSession.objects.get().revoked_at)
        self.device.refresh_from_db();self.assertIsNone(self.device.revoked_at)
        from families.access import guardian
        self.assertFalse(guardian(self.guardian,self.household.id))

    def test_active_incident_blocks_account_close_even_with_other_guardian(self):
        from families.models import Guardian
        from incidents.services import create_incident
        Guardian.objects.create(user=self.other,household=self.household)
        create_incident(self.actor,self.child.id,uuid.uuid4(),self.location)
        case=privacy.submit_request(self.guardian,uuid.uuid4(),'account_close')
        result=privacy.review_request(self.admin,case.id,'approved','Active incident must retain care continuity')
        self.assertEqual(result.status,'hold')
        self.guardian.refresh_from_db();self.assertTrue(self.guardian.is_active)

    def test_coordinator_cannot_close_account_while_owning_active_response(self):
        from incidents.services import create_incident,claim_ownership
        obj,_=create_incident(self.actor,self.child.id,uuid.uuid4(),self.location)
        claim_ownership(self.coord,obj.id)
        case=privacy.submit_request(self.coord,uuid.uuid4(),'account_close')
        result=privacy.review_request(self.admin,case.id,'approved','Current operator responsibility must be handed over first')
        self.assertEqual(result.status,'hold')
        self.coord.refresh_from_db();self.assertTrue(self.coord.is_active)
