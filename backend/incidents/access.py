from django.db.models import Q
from django.db import connection
from django.contrib.auth import get_user_model
from rest_framework.exceptions import PermissionDenied
from families.access import is_device, guardian, active_grants
from operations.models import Coordinator
from .models import Incident

def require_active_adult(actor):
    if is_device(actor):raise PermissionDenied('Active adult account required.')
    query=get_user_model().objects
    if connection.in_atomic_block:query=query.select_for_update(no_key=True)
    if not query.filter(pk=actor.pk,is_active=True).exists():
        raise PermissionDenied('Active adult account required.')

def coordinator(actor, incident):
    return not is_device(actor) and Coordinator.objects.filter(user=actor, user__is_active=True, region_id=incident.region_id).exists()

def require_coordinator(actor, incident):
    require_active_adult(actor)
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
        Q(child_id__in=active_grants(actor,'view_incidents').values('child_id')) |
        Q(region__coordinator__user=actor) |
        Q(assignments__team__members=actor, assignments__state__in=['accepted', 'en_route', 'arrived'])
    ).distinct()
