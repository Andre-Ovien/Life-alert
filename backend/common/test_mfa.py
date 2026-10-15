from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase,override_settings
from django.utils import timezone
import pyotp
from . import test_identity as identity_fixtures
from .models import StaffMFA,AdultTokenSession
from . import mfa

@override_settings(ENFORCE_STAFF_MFA=True)
class StaffMFATests(TestCase):
    setUpBase=identity_fixtures.IdentityTests.setUpBase
    tokens=identity_fixtures.IdentityTests.tokens
    def setUp(self):
        identity_fixtures.IdentityTests.setUp(self)
        self.fixed_time=timezone.now()
        clock=patch('common.mfa.timezone.now',return_value=self.fixed_time)
        clock.start();self.addCleanup(clock.stop)
        self.guardian.is_staff=True;self.guardian.save()
        self.tokens_value=self.tokens()
        self.client.credentials(HTTP_AUTHORIZATION='Bearer '+self.tokens_value['access_token'])
    def enroll(self):
        response=self.client.post('/api/v1/mobile/mfa/enroll/',{'password':self.password},format='json')
        self.assertEqual(response.status_code,201,response.data)
        return response.data['secret']
    def confirm(self,secret):
        result=self.client.post('/api/v1/mobile/mfa/confirm/',{'code':pyotp.TOTP(secret).at(self.fixed_time)},format='json')
        self.assertEqual(result.status_code,200,result.data)
        return result.data['recovery_codes']
    def test_staff_gate_enrollment_replay_recovery_and_session_scope(self):
        path=f'/api/v1/children/{self.child.id}/'
        self.assertEqual(self.client.get(path).status_code,403)
        secret=self.enroll();record=StaffMFA.objects.get()
        self.assertNotIn(secret,record.encrypted_secret)
        codes=self.confirm(secret)
        self.assertEqual(self.client.get(path).status_code,200)
        self.assertEqual(self.client.post('/api/v1/mobile/mfa/verify/',{'code':pyotp.TOTP(secret).at(self.fixed_time)},format='json').status_code,400)
        another=self.tokens()
        self.client.credentials(HTTP_AUTHORIZATION='Bearer '+another['access_token'])
        self.assertEqual(self.client.get(path).status_code,403)
        self.assertEqual(self.client.post('/api/v1/mobile/mfa/verify/',{'code':codes[0]},format='json').status_code,200)
        self.assertEqual(self.client.get(path).status_code,200)
        self.assertEqual(self.client.post('/api/v1/mobile/mfa/verify/',{'code':codes[0]},format='json').status_code,400)
        record.refresh_from_db();self.assertNotIn(codes[0],record.recovery_digests)
    def test_mfa_expiry_and_reenrollment_cannot_bypass_factor(self):
        secret=self.enroll();codes=self.confirm(secret)
        self.assertEqual(self.client.post('/api/v1/mobile/mfa/enroll/',{'password':self.password},format='json').status_code,400)
        session=AdultTokenSession.objects.get();session.mfa_verified_at=timezone.now()-timedelta(days=2);session.save()
        self.assertEqual(self.client.get('/api/v1/children/').status_code,403)
        result=self.client.post('/api/v1/mobile/mfa/disable/',{'password':self.password,'code':codes[1]},format='json')
        self.assertEqual(result.status_code,204,result.data)
        self.assertEqual(self.client.get('/api/v1/children/').status_code,403)
        self.assertFalse(StaffMFA.objects.exists())
    def test_nonstaff_and_child_are_not_gated_and_child_cannot_enroll(self):
        self.guardian.is_staff=False;self.guardian.save()
        self.assertEqual(self.client.get('/api/v1/children/').status_code,200)
        self.client.credentials(HTTP_AUTHORIZATION='Device '+self.token)
        self.assertEqual(self.client.get('/api/v1/incidents/').status_code,200)
        self.assertEqual(self.client.post('/api/v1/mobile/mfa/enroll/',{'password':self.password},format='json').status_code,403)
    def test_wrong_password_expired_setup_and_admin_override_are_blocked(self):
        self.assertEqual(self.client.post('/api/v1/mobile/mfa/enroll/',{'password':'wrong'},format='json').status_code,403)
        secret=self.enroll();record=StaffMFA.objects.get();record.enrollment_expires_at=timezone.now()-timedelta(seconds=1);record.save()
        self.assertEqual(self.client.post('/api/v1/mobile/mfa/confirm/',{'code':pyotp.TOTP(secret).at(self.fixed_time)},format='json').status_code,400)
        self.guardian.is_superuser=True;self.guardian.save()
        self.assertEqual(self.client.get('/api/v1/configuration/regions/').status_code,403)
