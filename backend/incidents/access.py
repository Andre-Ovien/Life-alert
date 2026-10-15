from django.db.models import Q
from rest_framework.exceptions import PermissionDenied
from families.access import is_device, guardian
from operations.models import Coordinator
from .models import Incident

def coordinator(actor, incident):
    return not is_device(actor) and Coordinator.objects.filter(user=actor, region_id=incident.region_id).exists()

def require_coordinator(actor, incident):
    if not coordinator(actor, incident):
        raise PermissionDenied('Regional coordinator required.')

def responder(actor, incident):
    return not is_device(actor) and incident.assignments.filter(
        team__members=actor, state__in=['accepted', 'en_route', 'arrived']).exists()

def visible_incidents(actor):
    if is_device(actor):
        return Incident.objects.filter(child=actor.device.child)
    return Incident.objects.filter(
        Q(child__household__guardians__user=actor) |
        Q(region__coordinator__user=actor) |
        Q(assignments__team__members=actor, assignments__state__in=['accepted', 'en_route', 'arrived'])
    ).distinct()
