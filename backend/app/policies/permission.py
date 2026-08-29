"""Permission system (US-6c).

Authorization ("what is this agent allowed to do at all") is a separate layer
from policy ("is this specific transaction within limits"). Both must pass.

The capability set is a module-level constant, not a database row and not
anything the LLM can address. There is no code path - by construction - through
which model output can add a capability to this set, which is what makes prompt
injection unable to escalate privilege: a hijacked prompt still cannot call
REFUND_PAYMENT, because no such tool is ever exposed to the model.
"""
from dataclasses import dataclass
from enum import StrEnum


class Capability(StrEnum):
    READ_PRODUCTS = "READ_PRODUCTS"
    SEARCH_PRODUCTS = "SEARCH_PRODUCTS"
    COMPARE_PRODUCTS = "COMPARE_PRODUCTS"
    CREATE_PURCHASE_INTENT = "CREATE_PURCHASE_INTENT"
    REQUEST_APPROVAL = "REQUEST_APPROVAL"
    CREATE_PAYMENT = "CREATE_PAYMENT"
    # explicitly denied to the buyer agent
    REFUND_PAYMENT = "REFUND_PAYMENT"
    MODIFY_USER_POLICY = "MODIFY_USER_POLICY"
    MODIFY_TRANSACTION_LIMIT = "MODIFY_TRANSACTION_LIMIT"
    # merchant-agent capabilities
    PROPOSE_BUNDLE = "PROPOSE_BUNDLE"
    READ_OPPORTUNITIES = "READ_OPPORTUNITIES"
    MODIFY_CATALOG_PRICING = "MODIFY_CATALOG_PRICING"


class PermissionDenied(Exception):
    """Raised when an agent attempts an action outside its granted capabilities."""

    def __init__(self, agent_id: str, capability: Capability | str):
        self.agent_id = agent_id
        self.capability = str(capability)
        super().__init__(
            f"Agent '{agent_id}' does not hold capability '{self.capability}'."
        )


@dataclass(frozen=True)
class PermissionSet:
    agent_id: str
    allowed: frozenset[Capability]
    denied: frozenset[Capability]

    def has(self, capability: Capability) -> bool:
        # denial is explicit and wins over any allow entry
        if capability in self.denied:
            return False
        return capability in self.allowed

    def assert_has(self, capability: Capability) -> None:
        if not self.has(capability):
            raise PermissionDenied(self.agent_id, capability)

    @property
    def allowed_names(self) -> list[str]:
        return sorted(str(c) for c in self.allowed)

    @property
    def denied_names(self) -> list[str]:
        return sorted(str(c) for c in self.denied)


BUYER_AGENT_PERMISSIONS = PermissionSet(
    agent_id="buyer_agent",
    allowed=frozenset(
        {
            Capability.READ_PRODUCTS,
            Capability.SEARCH_PRODUCTS,
            Capability.COMPARE_PRODUCTS,
            Capability.CREATE_PURCHASE_INTENT,
            Capability.REQUEST_APPROVAL,
            Capability.CREATE_PAYMENT,
        }
    ),
    denied=frozenset(
        {
            Capability.REFUND_PAYMENT,
            Capability.MODIFY_USER_POLICY,
            Capability.MODIFY_TRANSACTION_LIMIT,
        }
    ),
)

MERCHANT_AGENT_PERMISSIONS = PermissionSet(
    agent_id="merchant_agent",
    allowed=frozenset(
        {
            Capability.READ_PRODUCTS,
            Capability.READ_OPPORTUNITIES,
            Capability.PROPOSE_BUNDLE,
        }
    ),
    denied=frozenset(
        {
            # the merchant agent may propose discounts; it never writes prices
            Capability.MODIFY_CATALOG_PRICING,
            Capability.CREATE_PAYMENT,
            Capability.REFUND_PAYMENT,
            Capability.MODIFY_USER_POLICY,
        }
    ),
)

_REGISTRY = {
    BUYER_AGENT_PERMISSIONS.agent_id: BUYER_AGENT_PERMISSIONS,
    MERCHANT_AGENT_PERMISSIONS.agent_id: MERCHANT_AGENT_PERMISSIONS,
}


def permissions_for(agent_id: str) -> PermissionSet:
    """Look up an agent's fixed capability set. Unknown agents get nothing."""
    return _REGISTRY.get(
        agent_id, PermissionSet(agent_id=agent_id, allowed=frozenset(), denied=frozenset())
    )


def require_capability(agent_id: str, capability: Capability) -> PermissionSet:
    """Enforce a capability server-side. Raises PermissionDenied on failure."""
    perms = permissions_for(agent_id)
    perms.assert_has(capability)
    return perms
