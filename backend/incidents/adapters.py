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

class SimulatedNotifications:
    def send(self, notification_id):
        return 'simulated'  # Never "delivered" or human acknowledgement.

class LocalBilling:
    """Local entitlement ledger only; no payment processing or public activation."""
    def eligible(self, entitlement, at):
        return entitlement is not None and entitlement.eligible(at)
