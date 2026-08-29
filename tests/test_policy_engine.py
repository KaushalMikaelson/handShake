"""Policy engine unit tests (US-6).

Note what these tests do NOT need: a database, a network, a mock, or a fixture
beyond plain constructors. That is the point of keeping the engine dependency-
free - the component that guards money is the easiest one in the system to test
exhaustively.
"""
import pytest

from app.enums import AutonomyLevel
from app.policies import (
    BuyerPolicy,
    MerchantPolicy,
    PolicyContext,
    PolicyOutcome,
    ProposedBundle,
    ProposedPurchase,
    evaluate,
)

RUPEE = 100  # paise per rupee


def policy(**overrides) -> BuyerPolicy:
    base = dict(
        daily_budget=15_000 * RUPEE,
        monthly_budget=50_000 * RUPEE,
        max_transaction=10_000 * RUPEE,
        allowed_categories=["electronics"],
        blocked_categories=["financial_services"],
        require_approval_above=5_000 * RUPEE,
        allow_automatic_purchase_below=2_000 * RUPEE,
        autonomy_level=AutonomyLevel.BOUNDED_AUTO,
    )
    base.update(overrides)
    return BuyerPolicy(**base)


def merchant_policy(**overrides) -> MerchantPolicy:
    base = dict(
        max_discount_pct=10,
        max_campaign_budget=25_000 * RUPEE,
        auto_approve_bundle_discount_below_pct=5,
    )
    base.update(overrides)
    return MerchantPolicy(**base)


def purchase(amount_rupees: int, category="electronics", bundle=None) -> ProposedPurchase:
    return ProposedPurchase(
        amount=amount_rupees * RUPEE, category=category, product_id="p1",
        merchant_id="m1", bundle=bundle,
    )


# ---------------------------------------------------------------- categories
def test_blocked_category_is_blocked():
    d = evaluate(purchase(500, category="financial_services"), policy(), merchant_policy())
    assert d.outcome == PolicyOutcome.BLOCKED
    assert d.failed_rule == "category.blocked"
    assert not d.allowed


def test_category_not_on_allow_list_is_blocked():
    d = evaluate(purchase(500, category="jewellery"), policy(), merchant_policy())
    assert d.outcome == PolicyOutcome.BLOCKED
    assert d.failed_rule == "category.allowed"


def test_blocked_list_is_checked_before_allow_list():
    """Ordering matters: an explicitly blocked category must name the block rule."""
    p = policy(allowed_categories=["financial_services"], blocked_categories=["financial_services"])
    d = evaluate(purchase(500, category="financial_services"), p, merchant_policy())
    assert d.failed_rule == "category.blocked"


# ------------------------------------------------------------------- budgets
def test_over_max_transaction_is_blocked_with_named_rule():
    d = evaluate(purchase(11_999), policy(), merchant_policy())
    assert d.outcome == PolicyOutcome.BLOCKED
    assert d.failed_rule == "budget.max_transaction"
    assert "exceeds" in d.reason.lower()


def test_exactly_at_max_transaction_is_allowed():
    """Boundary: the limit is inclusive, so spending exactly the cap is fine."""
    d = evaluate(purchase(10_000), policy(), merchant_policy())
    assert d.outcome != PolicyOutcome.BLOCKED


def test_daily_budget_exhaustion_blocks():
    ctx = PolicyContext(spent_today=14_500 * RUPEE, spent_this_month=14_500 * RUPEE)
    d = evaluate(purchase(1_000), policy(), merchant_policy(), ctx)
    assert d.outcome == PolicyOutcome.BLOCKED
    assert d.failed_rule == "budget.daily"


def test_monthly_budget_exhaustion_blocks():
    ctx = PolicyContext(spent_today=0, spent_this_month=49_500 * RUPEE)
    d = evaluate(purchase(1_000), policy(), merchant_policy(), ctx)
    assert d.outcome == PolicyOutcome.BLOCKED
    assert d.failed_rule == "budget.monthly"


# ------------------------------------------------------------ autonomy levels
def test_below_auto_threshold_auto_approves():
    d = evaluate(purchase(299), policy(), merchant_policy())
    assert d.outcome == PolicyOutcome.AUTO_APPROVE
    assert d.allowed


def test_above_approval_threshold_requires_human():
    d = evaluate(purchase(8_999), policy(), merchant_policy())
    assert d.outcome == PolicyOutcome.REQUIRES_APPROVAL
    assert d.requires_human_approval


def test_amount_between_thresholds_defaults_to_asking():
    """The band between auto-buy and ask-above carries no automatic authority."""
    d = evaluate(purchase(3_000), policy(), merchant_policy())
    assert d.outcome == PolicyOutcome.REQUIRES_APPROVAL


def test_level_2_always_requires_approval_even_for_tiny_amounts():
    d = evaluate(purchase(10), policy(autonomy_level=AutonomyLevel.PREPARE), merchant_policy())
    assert d.outcome == PolicyOutcome.REQUIRES_APPROVAL


def test_level_1_never_authorises_a_purchase():
    d = evaluate(purchase(10), policy(autonomy_level=AutonomyLevel.RECOMMEND), merchant_policy())
    assert d.outcome == PolicyOutcome.RECOMMEND_ONLY
    assert not d.allowed


def test_autonomy_level_cannot_rescue_a_blocked_purchase():
    """Level 3 is not an override: hard limits are checked before autonomy."""
    d = evaluate(purchase(50_000), policy(autonomy_level=AutonomyLevel.BOUNDED_AUTO),
                 merchant_policy())
    assert d.outcome == PolicyOutcome.BLOCKED


# -------------------------------------------------------------- bundle limits
def test_bundle_discount_over_merchant_cap_is_blocked():
    bundle = ProposedBundle(discount_pct=40, bundle_price=6_000 * RUPEE,
                            list_price=10_000 * RUPEE)
    d = evaluate(purchase(6_000, bundle=bundle), policy(), merchant_policy(max_discount_pct=10))
    assert d.outcome == PolicyOutcome.BLOCKED
    assert d.failed_rule == "merchant.max_discount_pct"


def test_bundle_price_that_contradicts_its_own_discount_is_blocked():
    """The classic hallucination: says 10% off, quotes a 40%-off number."""
    bundle = ProposedBundle(discount_pct=10, bundle_price=6_000 * RUPEE,
                            list_price=10_000 * RUPEE)
    d = evaluate(purchase(6_000, bundle=bundle), policy(), merchant_policy())
    assert d.outcome == PolicyOutcome.BLOCKED
    assert d.failed_rule == "merchant.bundle_price_integrity"


def test_consistent_bundle_within_cap_passes():
    bundle = ProposedBundle(discount_pct=10, bundle_price=9_000 * RUPEE,
                            list_price=10_000 * RUPEE)
    d = evaluate(purchase(1_500, bundle=bundle), policy(), merchant_policy())
    assert d.outcome == PolicyOutcome.AUTO_APPROVE


# ---------------------------------------------------------------- reporting
def test_every_rule_is_reported_even_when_one_fails():
    """The UI needs the full per-rule report, not just the first failure."""
    d = evaluate(purchase(50_000), policy(), merchant_policy())
    rules = {c.rule for c in d.checks}
    assert {"category.blocked", "category.allowed", "budget.max_transaction",
            "budget.daily", "budget.monthly"} <= rules


def test_first_failure_determines_the_named_rule():
    """Over-limit AND over-budget: the earlier rule in the order is named."""
    ctx = PolicyContext(spent_today=14_900 * RUPEE)
    d = evaluate(purchase(50_000), policy(), merchant_policy(), ctx)
    assert d.failed_rule == "budget.max_transaction"


@pytest.mark.parametrize("amount", [0, 1, 199_999, 200_000, 200_001, 499_999, 500_000])
def test_engine_is_total_over_the_threshold_boundaries(amount):
    """No amount produces an undefined verdict around the threshold edges."""
    d = evaluate(ProposedPurchase(amount=amount, category="electronics"), policy(),
                 merchant_policy())
    assert d.outcome in set(PolicyOutcome)
