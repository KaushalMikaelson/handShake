"""Audit trail read endpoints (US-9). Read-only by construction - no writes here."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PurchaseIntent
from app.schemas.audit import AuditEventOut, AuditTimelineOut
from app.services import audit as audit_service

router = APIRouter(prefix="/audit", tags=["audit"])


def _out(event) -> AuditEventOut:
    return AuditEventOut(
        event_id=event.event_id,
        sequence=event.sequence,
        timestamp=event.timestamp,
        agent_id=event.agent_id,
        action=event.action,
        purchase_intent_id=event.purchase_intent_id,
        input_reference=event.input_reference,
        output_reference=event.output_reference,
        reason=event.reason,
        policy_result=event.policy_result,
        status=event.status,
    )


@router.get("/events", response_model=list[AuditEventOut])
def recent_events(
    db: Session = Depends(get_db), limit: int = Query(default=200, le=1000)
) -> list[AuditEventOut]:
    return [_out(e) for e in audit_service.recent(db, limit=limit)]


@router.get("/transactions", summary="Every transaction with a summary of its trail")
def transactions(db: Session = Depends(get_db), limit: int = Query(default=50, le=200)):
    intents = list(
        db.scalars(
            select(PurchaseIntent).order_by(PurchaseIntent.created_at.desc()).limit(limit)
        )
    )
    out = []
    for intent in intents:
        events = audit_service.timeline(db, intent.id)
        out.append(
            {
                "purchase_intent_id": intent.id,
                "status": intent.status,
                "amount": intent.amount,
                "product_id": intent.product_id,
                "created_at": intent.created_at,
                "event_count": len(events),
                "reasoning": intent.reasoning,
                "policy_result": intent.policy_result,
                "final_action": events[-1].action if events else None,
            }
        )
    return out


@router.get("/timeline/{purchase_intent_id}", response_model=AuditTimelineOut)
def timeline(purchase_intent_id: str, db: Session = Depends(get_db)) -> AuditTimelineOut:
    events = audit_service.timeline(db, purchase_intent_id)
    return AuditTimelineOut(
        purchase_intent_id=purchase_intent_id,
        event_count=len(events),
        events=[_out(e) for e in events],
    )
