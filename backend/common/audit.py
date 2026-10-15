from .models import AuditEvent

def audit(actor, action, obj, **facts):
    device = getattr(actor, 'device', None)
    return AuditEvent.objects.create(
        actor=None if device else actor, device_id=device.id if device else None,
        action=action, object_id=obj.id, facts=facts,
    )
