"""Append-only audit trail and webhook idempotency ledger (US-9, US-10.3).

Audit rows are immutable once written: the service layer exposes only an
append operation, and no UPDATE/DELETE path is reachable from the API.
"""
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base
from app.enums import AuditStatus


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    # `sequence` is the surrogate PK purely so it auto-increments portably
    # (SQLite only auto-generates on an INTEGER PRIMARY KEY; Postgres makes it
    # SERIAL). It gives the timeline a monotonic order that survives events
    # written inside the same clock tick.
    sequence: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )

    agent_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    purchase_intent_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    input_reference: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_reference: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    policy_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default=AuditStatus.OK, index=True)


class ProcessedWebhookEvent(Base):
    """Duplicate-delivery guard.

    The DB-level uniqueness constraint on event_id - not application logic - is
    what makes replay handling correct: a concurrent duplicate loses the insert
    race and is reported as DUPLICATE_IGNORED.
    """

    __tablename__ = "processed_webhook_events"

    event_id: Mapped[str] = mapped_column(String(128), primary_key=True, unique=True)
    event_type: Mapped[str] = mapped_column(String(64), default="")
    purchase_intent_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload_digest: Mapped[str] = mapped_column(String(64), default="")
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
