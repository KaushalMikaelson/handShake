"""Plain dataclasses the policy engine operates on.

These deliberately do NOT reference SQLAlchemy models. The engine takes values,
not rows, so a test can feed it a ProposedPurchase directly and assert on the
verdict without a database, a network, or a mock.
"""
from dataclasses import dataclass, field
from enum import StrEnum

from app.enums import AutonomyLevel


class PolicyOutcome(StrEnum):
    AUTO_APPROVE = "AUTO_APPROVE"
    REQUIRES_APPROVAL = "REQUIRES_APPROVAL"
    BLOCKED = "BLOCKED"
    RECOMMEND_ONLY = "RECOMMEND_ONLY"


@dataclass(frozen=True)
class BuyerPolicy:
    """Buyer-side config from PRD 3.4. All money in integer paise."""

    daily_budget: int
    monthly_budget: int
    max_transaction: int
    allowed_categories: list[str]
    blocked_categories: list[str]
    require_approval_above: int
    allow_automatic_purchase_below: int
    autonomy_level: AutonomyLevel = AutonomyLevel.BOUNDED_AUTO


@dataclass(frozen=True)
class MerchantPolicy:
    """Merchant-side config from PRD 3.4 - bounds the merchant agent's discounting."""

    max_discount_pct: int
    max_campaign_budget: int
    auto_approve_bundle_discount_below_pct: int


@dataclass(frozen=True)
class PolicyContext:
    """Rolling spend already committed by this buyer, read from the ledger."""

    spent_today: int = 0
    spent_this_month: int = 0


@dataclass(frozen=True)
class ProposedBundle:
    """Merchant agent's proposal - unauthorized until the engine passes it."""

    discount_pct: int
    bundle_price: int
    list_price: int


@dataclass(frozen=True)
class ProposedPurchase:
    """A PurchaseIntent reduced to exactly the facts the engine needs."""

    amount: int                  # paise, sourced from the catalog - never from an LLM
    category: str
    product_id: str = ""
    merchant_id: str = ""
    bundle: ProposedBundle | None = None


@dataclass(frozen=True)
class PolicyCheck:
    rule: str
    passed: bool
    detail: str
    limit: int | None = None
    observed: int | None = None


@dataclass
class PolicyDecision:
    allowed: bool
    outcome: PolicyOutcome
    reason: str
    evaluated_amount: int
    failed_rule: str | None = None
    checks: list[PolicyCheck] = field(default_factory=list)

    @property
    def requires_human_approval(self) -> bool:
        return self.outcome == PolicyOutcome.REQUIRES_APPROVAL

    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "decision": str(self.outcome),
            "failed_rule": self.failed_rule,
            "reason": self.reason,
            "evaluated_amount": self.evaluated_amount,
            "checks": [
                {
                    "rule": c.rule,
                    "passed": c.passed,
                    "detail": c.detail,
                    "limit": c.limit,
                    "observed": c.observed,
                }
                for c in self.checks
            ],
        }
