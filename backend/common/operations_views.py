from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from rest_framework import serializers,mixins,viewsets
from rest_framework.permissions import AllowAny,BasePermission
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from families.access import is_device
from common.audit import audit
from .models import AuditEvent
from .mfa import StaffMFAPermission

class AuditReader(BasePermission):
    def has_permission(self,request,view):
        return bool(request.user.is_authenticated and not is_device(request.user)
            and request.user.has_perm('common.read_audit_events') and StaffMFAPermission().has_permission(request,view))

class AuditSerializer(serializers.ModelSerializer):
    class Meta:
        model=AuditEvent
        fields=['id','created_at','actor','device_id','action','object_id','facts']
        read_only_fields=fields

class AuditView(mixins.ListModelMixin,viewsets.GenericViewSet):
    permission_classes=[AuditReader]
    serializer_class=AuditSerializer
    def get_queryset(self):
        query=AuditEvent.objects.all()
        # Require a purpose-scoped identifier; there is no general child-data search.
        try:
            import uuid
            object_id=uuid.UUID(self.request.query_params.get('object_id',''))
        except ValueError:raise ValidationError({'object_id':'An exact object UUID is required.'})
        return query.filter(object_id=object_id).order_by('-created_at','id')
    def list(self,request,*args,**kwargs):
        result=super().list(request,*args,**kwargs)
        # The audit read itself is append-only through this API.
        import uuid
        from types import SimpleNamespace
        audit(request.user,'audit.events_read',SimpleNamespace(id=uuid.UUID(request.query_params['object_id'])))
        return result

class ReadinessView(APIView):
    permission_classes=[AllowAny]
    authentication_classes=[]
    def get(self,request):
        try:
            with connection.cursor() as cursor:cursor.execute('SELECT 1');cursor.fetchone()
            executor=MigrationExecutor(connection)
            ready=not executor.migration_plan(executor.loader.graph.leaf_nodes())
            from django.conf import settings
            if not settings.DEBUG:
                from django.core.cache import cache
                cache.set('health-readiness',True,timeout=10)
                ready=ready and cache.get('health-readiness') is True
        except Exception:
            ready=False
        return Response({'status':'ready' if ready else 'unavailable',
            'scope':'database_migrations_and_configured_cache','live_service_ready':False},status=200 if ready else 503)
