"""Schemas for the AI layer.

Everything an LLM produces enters the system through one of these models. They
are validated by Pydantic at the boundary, which is what turns "the prompt asks
for JSON" into a runtime guarantee. Note what is deliberately absent: no model
here carries a chargeable amount that the system will actually bill. The
authoritative amount is always re-read from the catalog by product_id.
"""
from pydantic import BaseModel, Field, field_validator

from app.enums import AutonomyLevel


class ShoppingRequest(BaseModel):
    """US-2 - free-text goal from the user."""

    query: str = Field(min_length=1, max_length=2000)
    buyer_id: str | None = None
    accept_bundle: bool = Field(
        default=False,
        description=(
            "If true and the merchant agent offers a bundle, charge the bundle price "
            "instead of the single-product price. The bundle's discount is policy-checked "
            "either way."
        ),
    )
    # demo control: force the approval path or simulate payment failures
    simulate: str | None = Field(
        default=None,
        description="Optional failure-mode hook: 'payment_timeout' | 'payment_failed'",
    )


class ParsedIntent(BaseModel):
    """Structured form of the user's natural-language goal (US-2)."""

    category: str | None = None
    budget_max: int | None = Field(default=None, description="paise")
    preferred_brands: list[str] = Field(default_factory=list)
    use_case: str | None = None
    require_approval_above: int | None = Field(default=None, description="paise")
    needs_clarification: bool = False
    clarification_question: str | None = None

    @field_validator("preferred_brands", mode="before")
    @classmethod
    def _coerce_brands(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        return list(v)


class CandidateEvaluation(BaseModel):
    """US-3 - per-candidate verdict with a business-level justification."""

    product_id: str
    name: str
    price: int
    eligible: bool
    reasons: list[str] = Field(default_factory=list)
    rejection_reason: str | None = None
    justification: str = ""
    score: float = 0.0


class Recommendation(BaseModel):
    selected_product_id: str | None
    selected_name: str | None = None
    amount: int | None = None
    remaining_budget: int | None = None
    justification: str = ""
    candidates: list[CandidateEvaluation] = Field(default_factory=list)
    decision_factors: list[str] = Field(default_factory=list)
    llm_mode: str = "deterministic"


class BundleItem(BaseModel):
    product_id: str
    name: str
    price: int


class BundleOffer(BaseModel):
    """US-5 - merchant agent proposal. Unauthorized until the policy engine says so.

    `discount_pct` here is a *proposal*. The merchant policy check downstream is
    what authorizes it; the LLM proposes, it does not authorize.
    """

    offered: bool
    items: list[BundleItem] = Field(default_factory=list)
    bundle_price: int | None = None
    list_price: int | None = None
    discount_pct: int = 0
    reasoning: str = ""
    llm_mode: str = "deterministic"


class BuyerPolicyOut(BaseModel):
    daily_budget: int
    monthly_budget: int
    max_transaction: int
    allowed_categories: list[str]
    blocked_categories: list[str]
    require_approval_above: int
    allow_automatic_purchase_below: int
    autonomy_level: AutonomyLevel


class BuyerPolicyUpdate(BaseModel):
    daily_budget: int | None = Field(default=None, ge=0)
    monthly_budget: int | None = Field(default=None, ge=0)
    max_transaction: int | None = Field(default=None, ge=0)
    allowed_categories: list[str] | None = None
    blocked_categories: list[str] | None = None
    require_approval_above: int | None = Field(default=None, ge=0)
    allow_automatic_purchase_below: int | None = Field(default=None, ge=0)
    autonomy_level: AutonomyLevel | None = None


class BuyerStateOut(BaseModel):
    buyer_id: str
    name: str
    policy: BuyerPolicyOut
    spent_today: int
    spent_this_month: int
    remaining_today: int
    remaining_this_month: int
    permissions_allowed: list[str]
    permissions_denied: list[str]
