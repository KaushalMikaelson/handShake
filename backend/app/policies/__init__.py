"""Deterministic guardrails.

Hard rule for this package: NO LLM imports, NO network calls, NO database
access. Every module here is plain Python operating on dataclasses, so the
whole engine is unit-testable by constructing objects directly - zero mocking.
`tests/test_policy_isolation.py` asserts this boundary mechanically.
"""
from app.policies.engine import PolicyEngine, evaluate
from app.policies.models import (
    BuyerPolicy,
    MerchantPolicy,
    PolicyCheck,
    PolicyContext,
    PolicyDecision,
    PolicyOutcome,
    ProposedBundle,
    ProposedPurchase,
)
from app.policies.permission import (
    BUYER_AGENT_PERMISSIONS,
    Capability,
    PermissionDenied,
    PermissionSet,
    require_capability,
)

__all__ = [
    "BUYER_AGENT_PERMISSIONS",
    "BuyerPolicy",
    "Capability",
    "MerchantPolicy",
    "PermissionDenied",
    "PermissionSet",
    "PolicyCheck",
    "PolicyContext",
    "PolicyDecision",
    "PolicyEngine",
    "PolicyOutcome",
    "ProposedBundle",
    "ProposedPurchase",
    "evaluate",
    "require_capability",
]
