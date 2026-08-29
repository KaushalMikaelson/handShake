"""PurchaseIntent, human approval requests and payment transactions.

PurchaseIntent is the only interface between the LLM layer and the rest of the
system (US-4). It is a *request*, never an executable action: nothing in this
module can move money on its own.
"""
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base
from app.enums import ApprovalStatus, IntentStatus, TransactionStatus


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PurchaseIntent(Base):
    __tablename__ = "purchase_intents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    buyer_id: Mapped[str] = mapped_column(ForeignKey("buyers.id"), nullable=False, index=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), nullable=False)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False)

    # Authoritative chargeable amount, always re-read from the catalog by
    # product_id - never taken from LLM output (PRD 5.6 hallucination risk).
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # paise
    currency: Mapped[str] = mapped_column(String(3), default="INR")

    reasoning: Mapped[str] = mapped_column(Text, default="")
    parsed_intent: Mapped[dict] = mapped_column(JSON, default=dict)
    evaluation: Mapped[dict] = mapped_column(JSON, default=dict)   # per-candidate verdicts
    bundle: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    policy_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    trust: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    status: Mapped[str] = mapped_column(String(32), default=IntentStatus.CREATED, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ApprovalRequest(Base):
    """US-7 - the human gate. No timeout-to-approve path exists by design."""

    __tablename__ = "approval_requests"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    purchase_intent_id: Mapped[str] = mapped_column(
        ForeignKey("purchase_intents.id"), nullable=False, index=True
    )
    buyer_id: Mapped[str] = mapped_column(ForeignKey("buyers.id"), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default=ApprovalStatus.PENDING, index=True)
    decided_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    purchase_intent_id: Mapped[str] = mapped_column(
        ForeignKey("purchase_intents.id"), nullable=False, index=True
    )
    buyer_id: Mapped[str] = mapped_column(ForeignKey("buyers.id"), nullable=False)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), nullable=False)

    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # paise
    currency: Mapped[str] = mapped_column(String(3), default="INR")

    # Derived deterministically from purchase_intent_id so a retry of the same
    # intent can never create a second order (US-8).
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)

    razorpay_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    razorpay_payment_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    status: Mapped[str] = mapped_column(String(32), default=TransactionStatus.CREATED, index=True)
    failure_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
