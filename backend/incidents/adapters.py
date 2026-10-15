"""Only safe local adapters exist. No network, payment or outbound messaging."""
from dataclasses import dataclass
from django.conf import settings

@dataclass(frozen=True)
class ProviderResult:
    state: str
    evidence: str

class SimulatedEMS:
    def submit(self, operation_id):
        # Stable operation IDs are reserved for future provider idempotency.
        if settings.SIMULATED_EMS_OUTCOME == 'timeout':
            raise TimeoutError('Simulated provider timeout')
        return ProviderResult('provider_acknowledged', 'SIMULATION: receipt only; no contact or dispatch')

class RetryableNotificationFailure(Exception):
    pass

class UnknownNotificationOutcome(Exception):
    pass

class PermanentNotificationFailure(Exception):
    pass

class SimulatedNotifications:
    def send(self, notification_id):
        from .models import SimulatedDeliveryReceipt
        # Check durable receipt before failure injection. Reusing the same key
        # after a crash never repeats the logical simulated delivery.
        if SimulatedDeliveryReceipt.objects.filter(notification_id=notification_id).exists():
            return 'simulated'
        outcome = settings.SIM_NOTIFICATION_OUTCOME
        if outcome == 'retryable_failure':
            raise RetryableNotificationFailure()
        if outcome == 'unknown':
            raise UnknownNotificationOutcome()
        if outcome != 'success':
            raise PermanentNotificationFailure()
        SimulatedDeliveryReceipt.objects.get_or_create(notification_id=notification_id,
            defaults={'operation_id': notification_id})
        return 'simulated'  # Not real delivery or acknowledgement.

class LocalBilling:
    """Local entitlement ledger only; no payment processing or public activation."""
    def eligible(self, entitlement, at):
        return entitlement is not None and entitlement.eligible(at)
