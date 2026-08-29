"""Committed-spend accounting.

Budget consumption is recorded only when money actually moved (payment
captured). A blocked, rejected or abandoned intent never consumes budget, so a
buyer cannot be locked out of their own daily limit by an agent that merely
tried something.

Spend is persisted (PRD 5.7 Q3), so limits survive a restart and cannot be
cleared by starting a new session.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import SpendLedgerEntry
from app.policies.models import PolicyContext


def _now() -> datetime:
    return datetime.now(timezone.utc)


def spent_today(db: Session, buyer_id: str) -> int:
    start = _now().replace(hour=0, minute=0, second=0, microsecond=0)
    total = db.scalar(
        select(func.coalesce(func.sum(SpendLedgerEntry.amount), 0)).where(
            SpendLedgerEntry.buyer_id == buyer_id,
            SpendLedgerEntry.occurred_at >= start,
        )
    )
    return int(total or 0)


def spent_this_month(db: Session, buyer_id: str) -> int:
    now = _now()
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    total = db.scalar(
        select(func.coalesce(func.sum(SpendLedgerEntry.amount), 0)).where(
            SpendLedgerEntry.buyer_id == buyer_id,
            SpendLedgerEntry.occurred_at >= start,
        )
    )
    return int(total or 0)


def policy_context(db: Session, buyer_id: str) -> PolicyContext:
    return PolicyContext(
        spent_today=spent_today(db, buyer_id),
        spent_this_month=spent_this_month(db, buyer_id),
    )


def commit_spend(
    db: Session, *, buyer_id: str, purchase_intent_id: str, amount: int
) -> SpendLedgerEntry | None:
    """Record captured spend exactly once per purchase intent."""
    existing = db.scalar(
        select(SpendLedgerEntry).where(
            SpendLedgerEntry.purchase_intent_id == purchase_intent_id
        )
    )
    if existing is not None:
        return None
    entry = SpendLedgerEntry(
        id=f"spend_{uuid.uuid4().hex[:12]}",
        buyer_id=buyer_id,
        purchase_intent_id=purchase_intent_id,
        amount=amount,
        occurred_at=_now(),
    )
    db.add(entry)
    db.flush()
    return entry
