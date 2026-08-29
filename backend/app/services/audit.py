"""Append-only audit trail (US-9).

This module exposes exactly one write operation: `record`. There is no update
and no delete, anywhere in the codebase, for `audit_events` - which is what
makes "immutable once written" a property of the code rather than a promise in
a README.

Every state transition in the system funnels through here, including the
failure paths. An action that produced no audit event did not happen.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import AgentId, AuditAction, AuditStatus
from app.models import AuditEvent


def record(
    db: Session,
    *,
    agent_id: AgentId | str,
    action: AuditAction | str,
    reason: str = "",
    purchase_intent_id: str | None = None,
    input_reference: dict | None = None,
    output_reference: dict | None = None,
    policy_result: dict | None = None,
    status: AuditStatus | str = AuditStatus.OK,
    commit: bool = True,
) -> AuditEvent:
    """Append one immutable audit event."""
    event = AuditEvent(
        event_id=f"evt_{uuid.uuid4().hex[:16]}",
        timestamp=datetime.now(timezone.utc),
        agent_id=str(agent_id),
        action=str(action),
        purchase_intent_id=purchase_intent_id,
        input_reference=input_reference,
        output_reference=output_reference,
        reason=reason,
        policy_result=policy_result,
        status=str(status),
    )
    db.add(event)
    if commit:
        db.commit()
    else:
        db.flush()
    return event


def timeline(db: Session, purchase_intent_id: str) -> list[AuditEvent]:
    """Full ordered history for one transaction - what the Audit dashboard renders."""
    stmt = (
        select(AuditEvent)
        .where(AuditEvent.purchase_intent_id == purchase_intent_id)
        .order_by(AuditEvent.sequence.asc())
    )
    return list(db.scalars(stmt))


def recent(db: Session, limit: int = 200) -> list[AuditEvent]:
    stmt = select(AuditEvent).order_by(AuditEvent.sequence.desc()).limit(limit)
    return list(db.scalars(stmt))
