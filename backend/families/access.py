from rest_framework.exceptions import PermissionDenied
from .models import Guardian

def is_device(actor):
    return hasattr(actor, 'device')

def guardian(actor, household_id):
    return not is_device(actor) and Guardian.objects.filter(user=actor, household_id=household_id).exists()

def require_guardian(actor, household_id):
    if not guardian(actor, household_id):
        raise PermissionDenied('Guardian access required.')
