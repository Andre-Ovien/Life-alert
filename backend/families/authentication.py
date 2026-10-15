import hashlib
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .models import Device
from django.db.models import Q
from django.utils import timezone

class DevicePrincipal:
    is_authenticated = True
    is_active = True
    is_staff = False
    is_superuser = False
    def __init__(self, device):
        self.device = device
        self.pk = str(device.pk)

class DeviceAuthentication(BaseAuthentication):
    def authenticate_header(self, request):
        return 'Bearer' if request.headers.get('Authorization','').startswith('Bearer ') else 'Device'

    def authenticate(self, request):
        header = request.headers.get('Authorization', '')
        if not header.startswith('Device '):
            return None
        token = header[7:]
        if not 20 <= len(token) <= 200:
            raise AuthenticationFailed('Invalid device credential.')
        digest = hashlib.sha256(token.encode()).hexdigest()
        device = Device.objects.select_related('child').filter(token_digest=digest, revoked_at__isnull=True).filter(Q(expires_at__isnull=True)|Q(expires_at__gt=timezone.now())).first()
        if not device:
            raise AuthenticationFailed('Invalid or revoked device credential.')
        return DevicePrincipal(device), device
