from rest_framework.exceptions import PermissionDenied
from .models import Guardian

def is_device(actor):
    return hasattr(actor, 'device')

def guardian(actor, household_id):
    return not is_device(actor) and Guardian.objects.filter(user=actor, user__is_active=True, household_id=household_id).exists()

def require_guardian(actor, household_id):
    if not guardian(actor, household_id):
        raise PermissionDenied('Guardian access required.')

PERMISSIONS = {'view_care','view_incidents','request_help','manage_profile','manage_media','manage_devices'}

def active_grants(actor, permission):
    from django.db.models import Q
    from django.utils import timezone
    from .models import CaregiverGrant
    if is_device(actor) or permission not in PERMISSIONS:
        return CaregiverGrant.objects.none()
    return CaregiverGrant.objects.filter(user=actor, user__is_active=True, revoked_at__isnull=True,
        **{'can_'+permission: True}).filter(Q(expires_at__isnull=True)|Q(expires_at__gt=timezone.now()))

def child_access(actor, child, permission='view_care'):
    return guardian(actor, child.household_id) or active_grants(actor, permission).filter(child=child).exists()

def require_child_access(actor, child, permission='view_care'):
    if not child_access(actor, child, permission):
        raise PermissionDenied('Child permission required: '+permission)

def visible_children(actor, permission='view_care'):
    from django.db.models import Q
    from .models import Child
    if is_device(actor):
        return Child.objects.none()
    return Child.objects.filter(Q(household__guardians__user=actor)|Q(pk__in=active_grants(actor,permission).values('child_id'))).distinct()
