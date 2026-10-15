from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth.models import Permission
from incidents import tests as fixtures
from .models import AuditEvent

class OperationsTests(TestCase):
    setUp=fixtures.FoundationTests.setUp
    as_user=fixtures.FoundationTests.as_user
    def test_readiness_checks_database_without_private_diagnostics(self):
        response=self.client.get('/health/ready/')
        self.assertEqual(response.status_code,200,response.data)
        self.assertFalse(response.data['live_service_ready'])
        with patch('common.operations_views.MigrationExecutor',side_effect=RuntimeError('private DB details')):
            response=self.client.get('/health/ready/')
        self.assertEqual(response.status_code,503)
        self.assertNotIn('private',str(response.data))
    def test_audit_requires_explicit_permission_and_exact_object_scope(self):
        event=AuditEvent.objects.create(actor=self.guardian,action='test.structural',object_id=self.child.id)
        endpoint=f'/api/v1/audit-events/?object_id={self.child.id}'
        self.assertEqual(self.as_user(self.coord).get(endpoint).status_code,403)
        self.coord.user_permissions.add(Permission.objects.get(codename='read_audit_events'))
        from django.contrib.auth import get_user_model
        self.coord=get_user_model().objects.get(pk=self.coord.pk)
        self.assertEqual(self.as_user(self.coord).get('/api/v1/audit-events/').status_code,400)
        result=self.as_user(self.coord).get(endpoint)
        self.assertEqual(result.status_code,200,result.data)
        self.assertIn(str(event.id),[item['id'] for item in result.data['results']])
        self.assertNotIn('communication',str(result.data))
