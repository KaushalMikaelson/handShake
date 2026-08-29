"""Trust engine (US-11) and permission system (US-6c).

The single most important test in this file is
`test_maximum_trust_cannot_override_a_budget_limit` - it is the concrete proof
of Security Principle 7.
"""
import pytest

from app.enums import AutonomyLevel
from app.policies import (
    BuyerPolicy,
    Capability,
    MerchantPolicy,
    PermissionDenied,
    PolicyOutcome,
    ProposedPurchase,
    evaluate,
    require_capability,
)
from app.policies.permission import (
    BUYER_AGENT_PERMISSIONS,
    MERCHANT_AGENT_PERMISSIONS,
    permissions_for,
)
from app.trust import evaluate_trust


# ============================================================ trust engine
def test_seeded_merchant_scores_as_trustworthy(db, merchant):
    from app.models import Product

    products = db.query(Product).all()
    report = evaluate_trust(merchant, products)
    assert report.score == 100
    assert report.band == "HIGH"
    assert all(s.passed for s in report.signals)


def test_unverified_catalog_lowers_the_score(db, merchant):
    from app.models import Product

    merchant.verified_catalog = False
    products = db.query(Product).all()
    report = evaluate_trust(merchant, products)
    assert report.score == 80
    assert not next(s for s in report.signals if s.name == "catalog_verified").passed


def test_poor_fulfilment_history_lowers_the_score(db, merchant):
    from app.models import Product

    merchant.successful_transactions = 5
    merchant.failed_transactions = 20
    report = evaluate_trust(merchant, db.query(Product).all())
    assert not next(s for s in report.signals if s.name == "fulfilment_history").passed
    assert report.band in {"MODERATE", "LOW"}


def test_maximum_trust_cannot_override_a_budget_limit():
    """Security Principle 7, as an executable assertion.

    A merchant with a perfect trust score offering a Rs 90,000 product to a
    buyer with a Rs 70,000 limit is still BLOCKED. Trust is a ranking signal;
    it is not an input to the policy engine at all - note that this call cannot
    even pass a trust score, because the engine's signature has nowhere to put one.
    """
    policy = BuyerPolicy(
        daily_budget=10_000_000,
        monthly_budget=20_000_000,
        max_transaction=7_000_000,          # Rs 70,000
        allowed_categories=["electronics"],
        blocked_categories=[],
        require_approval_above=500_000,
        allow_automatic_purchase_below=200_000,
        autonomy_level=AutonomyLevel.BOUNDED_AUTO,
    )
    decision = evaluate(
        ProposedPurchase(amount=9_000_000, category="electronics"),   # Rs 90,000
        policy,
        MerchantPolicy(max_discount_pct=10, max_campaign_budget=0,
                       auto_approve_bundle_discount_below_pct=5),
    )
    assert decision.outcome == PolicyOutcome.BLOCKED
    assert decision.failed_rule == "budget.max_transaction"


def test_trust_report_declares_itself_advisory(db, merchant):
    from app.models import Product

    report = evaluate_trust(merchant, db.query(Product).all())
    assert "advisory" in report.advisory_note.lower()
    assert "cannot" in report.advisory_note.lower()


# ========================================================= permission system
def test_buyer_agent_holds_exactly_the_specified_capabilities():
    assert BUYER_AGENT_PERMISSIONS.allowed_names == [
        "COMPARE_PRODUCTS", "CREATE_PAYMENT", "CREATE_PURCHASE_INTENT",
        "READ_PRODUCTS", "REQUEST_APPROVAL", "SEARCH_PRODUCTS",
    ]
    assert BUYER_AGENT_PERMISSIONS.denied_names == [
        "MODIFY_TRANSACTION_LIMIT", "MODIFY_USER_POLICY", "REFUND_PAYMENT",
    ]


@pytest.mark.parametrize(
    "capability",
    [Capability.REFUND_PAYMENT, Capability.MODIFY_USER_POLICY,
     Capability.MODIFY_TRANSACTION_LIMIT],
)
def test_denied_capabilities_raise(capability):
    with pytest.raises(PermissionDenied):
        require_capability("buyer_agent", capability)


def test_merchant_agent_cannot_create_payments_or_write_pricing():
    for capability in (Capability.CREATE_PAYMENT, Capability.MODIFY_CATALOG_PRICING):
        with pytest.raises(PermissionDenied):
            require_capability("merchant_agent", capability)
    assert MERCHANT_AGENT_PERMISSIONS.has(Capability.PROPOSE_BUNDLE)


def test_unknown_agent_holds_no_capabilities():
    """Fail closed: an unregistered identity gets nothing, not everything."""
    perms = permissions_for("some_injected_agent")
    for capability in Capability:
        assert not perms.has(capability)


def test_permission_set_is_immutable_at_runtime():
    """The LLM cannot grant itself a permission - the set is a frozenset constant."""
    assert isinstance(BUYER_AGENT_PERMISSIONS.allowed, frozenset)
    with pytest.raises(AttributeError):
        BUYER_AGENT_PERMISSIONS.allowed.add(Capability.REFUND_PAYMENT)  # type: ignore[attr-defined]
    with pytest.raises(Exception):
        BUYER_AGENT_PERMISSIONS.agent_id = "root"  # type: ignore[misc]


def test_explicit_denial_beats_an_allow_entry():
    from app.policies.permission import PermissionSet

    perms = PermissionSet(
        agent_id="confused",
        allowed=frozenset({Capability.REFUND_PAYMENT}),
        denied=frozenset({Capability.REFUND_PAYMENT}),
    )
    assert perms.has(Capability.REFUND_PAYMENT) is False
