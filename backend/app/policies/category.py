"""Category rules - the first gate in the evaluation order (PRD 3.4)."""
from app.policies.models import BuyerPolicy, PolicyCheck, ProposedPurchase

RULE_BLOCKED_CATEGORY = "category.blocked"
RULE_ALLOWED_CATEGORY = "category.allowed"


def check_blocked_category(purchase: ProposedPurchase, policy: BuyerPolicy) -> PolicyCheck:
    blocked = [c.lower() for c in policy.blocked_categories]
    category = (purchase.category or "").lower()
    if category in blocked:
        return PolicyCheck(
            rule=RULE_BLOCKED_CATEGORY,
            passed=False,
            detail=f"Category '{purchase.category}' is on the buyer's blocked list.",
        )
    return PolicyCheck(
        rule=RULE_BLOCKED_CATEGORY,
        passed=True,
        detail=f"Category '{purchase.category}' is not blocked.",
    )


def check_allowed_category(purchase: ProposedPurchase, policy: BuyerPolicy) -> PolicyCheck:
    allowed = [c.lower() for c in policy.allowed_categories]
    category = (purchase.category or "").lower()
    if allowed and category not in allowed:
        return PolicyCheck(
            rule=RULE_ALLOWED_CATEGORY,
            passed=False,
            detail=(
                f"Category '{purchase.category}' is not in the buyer's allowed "
                f"categories ({', '.join(policy.allowed_categories)})."
            ),
        )
    return PolicyCheck(
        rule=RULE_ALLOWED_CATEGORY,
        passed=True,
        detail=f"Category '{purchase.category}' is explicitly allowed.",
    )
