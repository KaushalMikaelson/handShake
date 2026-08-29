"""Purchase intent, policy verdict, approval and transaction contracts."""
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.agents import BundleOffer, Recommendation


class PolicyCheckOut(BaseModel):
    """One deterministic rule evaluation, in the order the engine ran it."""

    rule: str
    passed: bool
    detail: str
    limit: int | None = None
    observed: int | None = None


class PolicyDecisionOut(BaseModel):
    allowed: bool
    decision: str          # AUTO_APPROVE | REQUIRES_APPROVAL | BLOCKED
    failed_rule: str | None = None
    reason: str
    checks: list[PolicyCheckOut] = Field(default_factory=list)
    evaluated_amount: int


class TrustOut(BaseModel):
    merchant_id: str
    score: int
    band: str
    signals: list[dict] = Field(default_factory=list)
    advisory_note: str


class TransactionOut(BaseModel):
    id: str
    purchase_intent_id: str
    amount: int
    currency: str
    status: str
    razorpay_order_id: str | None = None
    razorpay_payment_id: str | None = None
    idempotency_key: str
    failure_reason: str | None = None


class PurchaseIntentOut(BaseModel):
    intent_id: str
    buyer_id: str
    merchant_id: str
    product_id: str
    amount: int
    currency: str
    reasoning: str
    status: str
    created_at: datetime


class ApprovalOut(BaseModel):
    approval_id: str
    purchase_intent_id: str
    buyer_id: str
    amount: int
    status: str
    context: dict
    created_at: datetime
    decided_at: datetime | None = None
    decided_by: str | None = None


class ApprovalDecision(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")
    actor: str = "human"
    note: str | None = None


class ShopResponse(BaseModel):
    """The full result of one shopping run - what the Buyer dashboard renders."""

    status: str
    stage: str
    message: str
    needs_clarification: bool = False
    clarification_question: str | None = None
    parsed_intent: dict | None = None
    recommendation: Recommendation | None = None
    bundle: BundleOffer | None = None
    trust: TrustOut | None = None
    policy: PolicyDecisionOut | None = None
    intent: PurchaseIntentOut | None = None
    approval: ApprovalOut | None = None
    transaction: TransactionOut | None = None
    razorpay_called: bool = False
