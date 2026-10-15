from datetime import timedelta
from unittest.mock import patch
from django.test import TestCase,override_settings
from django.utils import timezone
from django.core.cache import cache
from rest_framework.test import APIClient
from incidents import tests as fixtures
from . import identity
from .models import AdultTokenSession,AccountChallenge,VerifiedContact,IdentityDispatch

class IdentityTests(TestCase):
    setUpBase=fixtures.FoundationTests.setUp
    def setUp(self):
        self.setUpBase();cache.clear()
        self.password='Synthetic-Test-Password-742!'
        self.guardian.set_password(self.password);self.guardian.email='synthetic@example.invalid';self.guardian.save()
        self.client=APIClient()
    def tokens(self):return identity.issue_tokens(self.guardian.username,self.password)

    def test_tokens_are_hashed_and_allow_only_actual_user_scope(self):
        tokens=self.tokens();session=AdultTokenSession.objects.get()
        self.assertNotEqual(session.access_digest,tokens['access_token'])
        self.assertNotEqual(session.refresh_digest,tokens['refresh_token'])
        self.client.credentials(HTTP_AUTHORIZATION='Bearer '+tokens['access_token'])
        response=self.client.get(f'/api/v1/children/{self.child.id}/')
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.client.get('/api/v1/configuration/regions/').status_code,403)

    def test_access_expiry_and_logout_revoke_mobile_access_not_child_device(self):
        tokens=self.tokens()
        self.client.credentials(HTTP_AUTHORIZATION='Bearer '+tokens['access_token'])
        response=self.client.post('/api/v1/mobile/logout/',{},format='json')
        self.assertEqual(response.status_code,204,response.data)
        self.assertEqual(self.client.get('/api/v1/children/').status_code,401)
        self.client.credentials(HTTP_AUTHORIZATION='Device '+self.token)
        self.assertEqual(self.client.get('/api/v1/incidents/').status_code,200)
        self.device.refresh_from_db();self.assertIsNone(self.device.revoked_at)

    def test_refresh_rotates_and_replay_revocation_commits(self):
        first=self.tokens();second=identity.refresh_tokens(first['refresh_token'])
        self.assertNotEqual(first['access_token'],second['access_token'])
        self.client.credentials(HTTP_AUTHORIZATION='Bearer '+first['access_token'])
        self.assertEqual(self.client.get('/api/v1/children/').status_code,401)
        with self.assertRaisesMessage(Exception,'replayed'):
            identity.refresh_tokens(first['refresh_token'])
        self.assertIsNotNone(AdultTokenSession.objects.get().revoked_at)
        self.client.credentials(HTTP_AUTHORIZATION='Bearer '+second['access_token'])
        self.assertEqual(self.client.get('/api/v1/children/').status_code,401)

    def test_expired_or_disabled_user_credentials_fail(self):
        tokens=self.tokens();session=AdultTokenSession.objects.get()
        session.access_expires_at=timezone.now()-timedelta(seconds=1);session.save()
        self.client.credentials(HTTP_AUTHORIZATION='Bearer '+tokens['access_token'])
        self.assertEqual(self.client.get('/api/v1/children/').status_code,401)
        self.guardian.is_active=False;self.guardian.save()
        with self.assertRaises(Exception):identity.refresh_tokens(tokens['refresh_token'])
        with self.assertRaises(Exception):identity.issue_tokens(self.guardian.username,self.password)

    @override_settings(REQUIRE_VERIFIED_ADULT_CONTACT=True)
    def test_contact_proof_required_when_enabled_and_never_grants_care_authority(self):
        with self.assertRaisesMessage(Exception,'Contact verification'):
            self.tokens()
        captured={}
        def delivery(adapter,challenge,raw):captured.update(token=raw,challenge=challenge)
        with patch('common.identity.SimulatedIdentityDelivery.deliver',delivery):
            challenge=identity.create_challenge(self.guardian,'contact',self.guardian.email)
        identity.consume_challenge(captured['token'],'contact')
        self.assertTrue(self.tokens()['access_token'])
        self.assertTrue(VerifiedContact.objects.filter(user=self.guardian).exists())
        from families.models import AuthorityRecord
        self.assertFalse(AuthorityRecord.objects.exists())
        with self.assertRaises(Exception):identity.consume_challenge(captured['token'],'contact')

    def test_recovery_response_does_not_enumerate_accounts_or_expose_tokens(self):
        one=self.client.post('/api/v1/mobile/recovery/',{'username':'unknown-account'},format='json')
        two=self.client.post('/api/v1/mobile/recovery/',{'username':self.guardian.username},format='json')
        self.assertEqual(one.status_code,202);self.assertEqual(one.data,two.data)
        self.assertNotIn('token',two.data)
        self.assertFalse(IdentityDispatch.objects.exists())

    def test_recovery_uses_single_use_challenge_and_revokes_old_sessions(self):
        self.tokens()
        VerifiedContact.objects.create(user=self.guardian,email=self.guardian.email,verified_at=timezone.now())
        captured={}
        with patch('common.identity.SimulatedIdentityDelivery.deliver',lambda adapter,challenge,raw:captured.update(token=raw)):
            identity.request_recovery(self.guardian.username)
        new_password='Another-Synthetic-Password-934!'
        identity.consume_challenge(captured['token'],'recovery',new_password)
        self.guardian.refresh_from_db();self.assertTrue(self.guardian.check_password(new_password))
        self.assertIsNotNone(AdultTokenSession.objects.get().revoked_at)
        with self.assertRaises(Exception):identity.consume_challenge(captured['token'],'recovery',new_password)
        self.assertTrue(identity.issue_tokens(self.guardian.username,new_password))

    def test_expired_challenge_or_weak_new_password_does_not_change_account(self):
        captured={}
        with patch('common.identity.SimulatedIdentityDelivery.deliver',lambda adapter,challenge,raw:captured.update(token=raw)):
            challenge=identity.create_challenge(self.guardian,'recovery',self.guardian.email)
        with self.assertRaises(Exception):identity.consume_challenge(captured['token'],'recovery','password')
        challenge.refresh_from_db();self.assertIsNone(challenge.used_at)
        challenge.expires_at=timezone.now()-timedelta(seconds=1);challenge.save()
        with self.assertRaises(Exception):identity.consume_challenge(captured['token'],'recovery','Fresh-Synthetic-Password-734!')
        self.guardian.refresh_from_db();self.assertTrue(self.guardian.check_password(self.password))

    def test_public_mobile_endpoints_return_only_once_secrets_and_no_cookie_session(self):
        response=self.client.post('/api/v1/mobile/token/',{'username':self.guardian.username,'password':self.password},format='json')
        self.assertEqual(response.status_code,200,response.data)
        self.assertNotIn('sessionid',response.cookies)
        self.assertEqual(response.data['token_type'],'Bearer')
        refreshed=self.client.post('/api/v1/mobile/refresh/',{'refresh_token':response.data['refresh_token']},format='json')
        self.assertEqual(refreshed.status_code,200,refreshed.data)
        contact=self.client.post('/api/v1/mobile/contact-challenges/',{'username':self.guardian.username,'password':self.password,'email':'new-synthetic@example.invalid'},format='json')
        self.assertEqual(contact.status_code,202,contact.data)
        self.assertNotIn('token',contact.data)
        self.assertEqual(IdentityDispatch.objects.get().status,'simulated')
