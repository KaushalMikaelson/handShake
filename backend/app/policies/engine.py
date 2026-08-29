"""The deterministic policy engine (US-6).

Evaluation order is fixed and matches PRD 3.4:

    1. category allowed?                (blocked list, then allow list)
    2. within max_transaction?
    3. within remaining daily budget?   (and monthly)
    4. bundle discount within the merchant's max_discount_pct?

Every rule is evaluated so the UI can show a complete per-rule report, but the
FIRST failure determines the verdict and names `failed_rule`. A single failed
check produces BLOCKED - and BLOCKED means the Razorpay client is never
constructed or called, which `tests/test_failure_modes.py` asserts by counting
calls on the payment client.

No LLM output reaches this module except as already-validated scalars, and
`purchase.amount` is always catalog-sourced.
"""
from app.policies import budget as budget_rules
from app.policies import category as category_rules
from app.policies.approval import route_authority
from app.policies.models import (
    BuyerPolicy,
    MerchantPolicy,
    PolicyCheck,
    PolicyContext,
    PolicyDecision,
    PolicyOutcome,
    ProposedPurchase,
)


class PolicyEngine:
    """Stateless evaluator. Construct freely; it holds no connections."""

    def evaluate(
        self,
        purchase: ProposedPurchase,
        policy: BuyerPolicy,
        merchant_policy: MerchantPolicy,
        context: PolicyContext | None = None,
    ) -> PolicyDecision:
        context = context or PolicyContext()
        checks: list[PolicyCheck] = [
            category_rules.check_blocked_category(purchase, policy),
            category_rules.check_allowed_category(purchase, policy),
            budget_rules.check_max_transaction(purchase, policy),
            budget_rules.check_daily_budget(purchase, policy, context),
            budget_rules.check_monthly_budget(purchase, policy, context),
        ]

        bundle_discount = budget_rules.check_bundle_discount(purchase, merchant_policy)
        if bundle_discount is not None:
            checks.append(bundle_discount)

        bundle_integrity = budget_rules.check_bundle_price_integrity(purchase)
        if bundle_integrity is not None:
            checks.append(bundle_integrity)

        first_failure = next((c for c in checks if not c.passed), None)
        if first_failure is not None:
            return PolicyDecision(
                allowed=False,
                outcome=PolicyOutcome.BLOCKED,
                reason=first_failure.detail,
                evaluated_amount=purchase.amount,
                failed_rule=first_failure.rule,
                checks=checks,
            )

        outcome, reason = route_authority(purchase, policy)
        return PolicyDecision(
            allowed=outcome != PolicyOutcome.RECOMMEND_ONLY,
            outcome=outcome,
            reason=reason,
            evaluated_amount=purchase.amount,
            failed_rule=None,
            checks=checks,
        )


_ENGINE = PolicyEngine()


def evaluate(
    purchase: ProposedPurchase,
    policy: BuyerPolicy,
    merchant_policy: MerchantPolicy,
    context: PolicyContext | None = None,
) -> PolicyDecision:
    """Module-level convenience wrapper around the shared stateless engine."""
    return _ENGINE.evaluate(purchase, policy, merchant_policy, context)
