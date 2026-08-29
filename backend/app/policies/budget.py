"""Budget rules - per-transaction ceiling and rolling daily/monthly spend."""
from app.policies.models import (
    BuyerPolicy,
    MerchantPolicy,
    PolicyCheck,
    PolicyContext,
    ProposedPurchase,
)
from app.services.money import format_inr

RULE_MAX_TRANSACTION = "budget.max_transaction"
RULE_DAILY_BUDGET = "budget.daily"
RULE_MONTHLY_BUDGET = "budget.monthly"
RULE_BUNDLE_DISCOUNT = "merchant.max_discount_pct"
RULE_BUNDLE_PRICE_INTEGRITY = "merchant.bundle_price_integrity"


def check_max_transaction(purchase: ProposedPurchase, policy: BuyerPolicy) -> PolicyCheck:
    over = purchase.amount - policy.max_transaction
    if over > 0:
        return PolicyCheck(
            rule=RULE_MAX_TRANSACTION,
            passed=False,
            detail=(
                f"Amount {format_inr(purchase.amount)} exceeds the per-transaction "
                f"limit of {format_inr(policy.max_transaction)} by {format_inr(over)}."
            ),
            limit=policy.max_transaction,
            observed=purchase.amount,
        )
    return PolicyCheck(
        rule=RULE_MAX_TRANSACTION,
        passed=True,
        detail=(
            f"{format_inr(purchase.amount)} is within the per-transaction limit of "
            f"{format_inr(policy.max_transaction)}."
        ),
        limit=policy.max_transaction,
        observed=purchase.amount,
    )


def check_daily_budget(
    purchase: ProposedPurchase, policy: BuyerPolicy, context: PolicyContext
) -> PolicyCheck:
    projected = context.spent_today + purchase.amount
    remaining = policy.daily_budget - context.spent_today
    if projected > policy.daily_budget:
        return PolicyCheck(
            rule=RULE_DAILY_BUDGET,
            passed=False,
            detail=(
                f"Purchase would take today's spend to {format_inr(projected)}, over the "
                f"daily budget of {format_inr(policy.daily_budget)} "
                f"(only {format_inr(max(remaining, 0))} left today)."
            ),
            limit=policy.daily_budget,
            observed=projected,
        )
    return PolicyCheck(
        rule=RULE_DAILY_BUDGET,
        passed=True,
        detail=(
            f"Today's spend would be {format_inr(projected)} of "
            f"{format_inr(policy.daily_budget)}."
        ),
        limit=policy.daily_budget,
        observed=projected,
    )


def check_monthly_budget(
    purchase: ProposedPurchase, policy: BuyerPolicy, context: PolicyContext
) -> PolicyCheck:
    projected = context.spent_this_month + purchase.amount
    if projected > policy.monthly_budget:
        return PolicyCheck(
            rule=RULE_MONTHLY_BUDGET,
            passed=False,
            detail=(
                f"Purchase would take this month's spend to {format_inr(projected)}, over "
                f"the monthly budget of {format_inr(policy.monthly_budget)}."
            ),
            limit=policy.monthly_budget,
            observed=projected,
        )
    return PolicyCheck(
        rule=RULE_MONTHLY_BUDGET,
        passed=True,
        detail=(
            f"This month's spend would be {format_inr(projected)} of "
            f"{format_inr(policy.monthly_budget)}."
        ),
        limit=policy.monthly_budget,
        observed=projected,
    )


def check_bundle_discount(
    purchase: ProposedPurchase, merchant_policy: MerchantPolicy
) -> PolicyCheck | None:
    """The merchant agent proposes a discount; this is what authorizes it (US-5)."""
    if purchase.bundle is None:
        return None
    proposed = purchase.bundle.discount_pct
    if proposed > merchant_policy.max_discount_pct:
        return PolicyCheck(
            rule=RULE_BUNDLE_DISCOUNT,
            passed=False,
            detail=(
                f"Proposed bundle discount of {proposed}% exceeds the merchant's "
                f"authorised maximum of {merchant_policy.max_discount_pct}%."
            ),
            limit=merchant_policy.max_discount_pct,
            observed=proposed,
        )
    return PolicyCheck(
        rule=RULE_BUNDLE_DISCOUNT,
        passed=True,
        detail=(
            f"Bundle discount of {proposed}% is within the merchant's authorised "
            f"maximum of {merchant_policy.max_discount_pct}%."
        ),
        limit=merchant_policy.max_discount_pct,
        observed=proposed,
    )


def check_bundle_price_integrity(purchase: ProposedPurchase) -> PolicyCheck | None:
    """Guard against an agent-quoted bundle price that doesn't match its own discount.

    Catches the hallucination case where the LLM says "10% off" but quotes a
    number that is actually 40% off. The arithmetic - not the text - decides.
    """
    if purchase.bundle is None:
        return None
    bundle = purchase.bundle
    expected = bundle.list_price - (bundle.list_price * bundle.discount_pct) // 100
    if bundle.bundle_price != expected:
        return PolicyCheck(
            rule=RULE_BUNDLE_PRICE_INTEGRITY,
            passed=False,
            detail=(
                f"Quoted bundle price {format_inr(bundle.bundle_price)} does not match "
                f"{bundle.discount_pct}% off {format_inr(bundle.list_price)} "
                f"(expected {format_inr(expected)})."
            ),
            limit=expected,
            observed=bundle.bundle_price,
        )
    return PolicyCheck(
        rule=RULE_BUNDLE_PRICE_INTEGRITY,
        passed=True,
        detail=(
            f"Bundle price {format_inr(bundle.bundle_price)} matches "
            f"{bundle.discount_pct}% off {format_inr(bundle.list_price)}."
        ),
        limit=expected,
        observed=bundle.bundle_price,
    )
