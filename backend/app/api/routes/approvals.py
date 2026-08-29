"""Human approval gate (US-7).

Approve and Reject are the only two transitions. There is no timeout path that
grants approval: an untouched request stays PENDING forever, which is the safe
default.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.enums import AgentId, ApprovalStatus, AuditAction, AuditStatus, IntentStatus
from app.models import ApprovalRequest, PurchaseIntent
from app.schemas.commerce import ApprovalDecision, ApprovalOut, ShopResponse
from app.services import audit
from app.services.orchestrator import _approval_out, _intent_out, execute_payment

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("", response_model=list[ApprovalOut])
def list_approvals(
    db: Session = Depends(get_db), status_filter: str | None = None
) -> list[ApprovalOut]:
    stmt = select(ApprovalRequest).order_by(ApprovalRequest.created_at.desc())
    if status_filter:
        stmt = stmt.where(ApprovalRequest.status == status_filter)
    return [_approval_out(a) for a in db.scalars(stmt)]


@router.get("/{approval_id}", response_model=ApprovalOut)
def get_approval(approval_id: str, db: Session = Depends(get_db)) -> ApprovalOut:
    approval = db.get(ApprovalRequest, approval_id)
    if approval is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Approval request not found")
    return _approval_out(approval)


@router.post("/{approval_id}/decision", response_model=ShopResponse)
def decide(
    approval_id: str,
    decision: ApprovalDecision,
    db: Session = Depends(get_db),
    simulate: str | None = None,
) -> ShopResponse:
    approval = db.get(ApprovalRequest, approval_id)
    if approval is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Approval request not found")
    if approval.status != ApprovalStatus.PENDING:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Approval already {approval.status.lower()}; decisions are final.",
        )

    intent = db.get(PurchaseIntent, approval.purchase_intent_id)

    # --- Reject: terminate, log, never call the gateway ---
    if decision.decision == "reject":
        approval.status = ApprovalStatus.REJECTED
        approval.decided_by = decision.actor
        approval.decided_at = datetime.now(timezone.utc)
        intent.status = IntentStatus.REJECTED
        db.commit()
        audit.record(
            db,
            agent_id=AgentId.HUMAN,
            action=AuditAction.APPROVAL_REJECTED,
            reason=decision.note or "Purchase rejected by the buyer.",
            purchase_intent_id=intent.id,
            status=AuditStatus.BLOCKED,
            output_reference={"razorpay_called": False},
        )
        return ShopResponse(
            status="rejected",
            stage="approval",
            message="Purchase rejected. No payment was attempted.",
            intent=_intent_out(intent),
            approval=_approval_out(approval),
            razorpay_called=False,
        )

    # --- Approve: this is the only human-driven path to the gateway ---
    approval.status = ApprovalStatus.APPROVED
    approval.decided_by = decision.actor
    approval.decided_at = datetime.now(timezone.utc)
    intent.status = IntentStatus.APPROVED
    db.commit()
    audit.record(
        db,
        agent_id=AgentId.HUMAN,
        action=AuditAction.APPROVAL_GRANTED,
        reason=decision.note or f"Purchase approved by {decision.actor}.",
        purchase_intent_id=intent.id,
        output_reference={"approval_id": approval.id, "amount": approval.amount},
    )

    txn_out, txn_status, message = execute_payment(db, intent=intent, simulate=simulate)
    return ShopResponse(
        status=txn_status,
        stage="payment",
        message=message,
        intent=_intent_out(intent),
        approval=_approval_out(approval),
        transaction=txn_out,
        razorpay_called=True,
    )
