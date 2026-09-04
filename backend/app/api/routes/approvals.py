"""Human approval gate (US-7).

Approve and Reject are the only two transitions. There is no timeout path that
grants approval: an untouched request stays PENDING forever, which is the safe
default.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_user
from app.config import settings
from app.database import get_db
from app.enums import AgentId, ApprovalStatus, AuditAction, AuditStatus, IntentStatus, UserRole
from app.models import ApprovalRequest, PurchaseIntent, User
from app.schemas.commerce import ApprovalDecision, ApprovalOut, ShopResponse
from app.services import audit
from app.services.orchestrator import _approval_out, _intent_out, execute_payment

router = APIRouter(prefix="/approvals", tags=["approvals"])


def _assert_owner(approval: ApprovalRequest, user: User) -> None:
    """A purchase may only be decided by the buyer whose money it is.

    Before authentication existed, any caller could approve any pending
    request. Ownership is now checked server-side on every decision.
    """
    if user.role == str(UserRole.ADMIN):
        return
    if approval.buyer_id != user.buyer_id:
        # 404, not 403: a stranger should not learn that this approval exists.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Approval request not found")


@router.get("", response_model=list[ApprovalOut])
def list_approvals(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    status_filter: str | None = None,
) -> list[ApprovalOut]:
    """Only ever the signed-in buyer's own approvals."""
    stmt = select(ApprovalRequest).order_by(ApprovalRequest.created_at.desc())
    if user.role != str(UserRole.ADMIN):
        stmt = stmt.where(ApprovalRequest.buyer_id == user.buyer_id)
    if status_filter:
        stmt = stmt.where(ApprovalRequest.status == status_filter)
    return [_approval_out(a) for a in db.scalars(stmt)]


@router.get("/{approval_id}", response_model=ApprovalOut)
def get_approval(
    approval_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> ApprovalOut:
    approval = db.get(ApprovalRequest, approval_id)
    if approval is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Approval request not found")
    _assert_owner(approval, user)
    return _approval_out(approval)


@router.post("/{approval_id}/decision", response_model=ShopResponse)
def decide(
    approval_id: str,
    decision: ApprovalDecision,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
    simulate: str | None = None,
) -> ShopResponse:
    approval = db.get(ApprovalRequest, approval_id)
    if approval is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Approval request not found")
    _assert_owner(approval, user)
    # The actor is taken from the session, never from the request body -
    # otherwise the audit trail records whatever the caller claimed to be.
    actor = f"{user.name} <{user.email}>"
    if approval.status != ApprovalStatus.PENDING:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Approval already {approval.status.lower()}; decisions are final.",
        )

    intent = db.get(PurchaseIntent, approval.purchase_intent_id)

    # --- Reject: terminate, log, never call the gateway ---
    if decision.decision == "reject":
        approval.status = ApprovalStatus.REJECTED
        approval.decided_by = actor
        approval.decided_at = datetime.now(timezone.utc)
        intent.status = IntentStatus.REJECTED
        db.commit()
        audit.record(
            db,
            agent_id=AgentId.HUMAN,
            action=AuditAction.APPROVAL_REJECTED,
            reason=decision.note or f"Purchase rejected by {actor}.",
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
    approval.decided_by = actor
    approval.decided_at = datetime.now(timezone.utc)
    intent.status = IntentStatus.APPROVED
    db.commit()
    audit.record(
        db,
        agent_id=AgentId.HUMAN,
        action=AuditAction.APPROVAL_GRANTED,
        reason=decision.note or f"Purchase approved by {actor}.",
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
        razorpay_key_id=settings.razorpay_key_id if settings.razorpay_live_mode else None,
    )
