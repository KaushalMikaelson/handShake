"""Buyer identity, policy config and persisted spend ledger.

"Budget spent so far" is persisted per buyer in the database rather than held
in session state (PRD 5.7 open question 3), so budget enforcement survives a
restart and cannot be reset by starting a new session.
"""
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base
from app.enums import AutonomyLevel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Buyer(Base):
    __tablename__ = "buyers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    # --- buyer-side policy config (PRD 3.4), all money in paise ---
    daily_budget: Mapped[int] = mapped_column(Integer, default=1_500_000)
    monthly_budget: Mapped[int] = mapped_column(Integer, default=5_000_000)
    max_transaction: Mapped[int] = mapped_column(Integer, default=1_000_000)
    allowed_categories: Mapped[list] = mapped_column(JSON, default=lambda: ["electronics"])
    blocked_categories: Mapped[list] = mapped_column(JSON, default=lambda: ["financial_services"])
    require_approval_above: Mapped[int] = mapped_column(Integer, default=500_000)
    allow_automatic_purchase_below: Mapped[int] = mapped_column(Integer, default=200_000)

    autonomy_level: Mapped[str] = mapped_column(String(32), default=AutonomyLevel.BOUNDED_AUTO)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class SpendLedgerEntry(Base):
    """Append-only record of committed spend, used to compute rolling budgets.

    An entry is written only when money has actually moved (payment captured),
    so a blocked or rejected intent never consumes budget.
    """

    __tablename__ = "spend_ledger"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    buyer_id: Mapped[str] = mapped_column(ForeignKey("buyers.id"), nullable=False, index=True)
    purchase_intent_id: Mapped[str] = mapped_column(String(64), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # paise
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )
