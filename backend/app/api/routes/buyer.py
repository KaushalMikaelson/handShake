"""Buyer-facing endpoints: shop, policy, state, payment verification."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import current_buyer, current_user
from app.config import settings
from app.database import get_db
from app.enums import (
    AgentId,
    AuditAction,
    AuditStatus,
    AutonomyLevel,
    IntentStatus,
    TransactionStatus,
)
from app.models import Buyer, PurchaseIntent, Transaction, User
from app.payments.razorpay_service import get_payment_client
from app.policies.permission import BUYER_AGENT_PERMISSIONS
from app.schemas.agents import (
    BuyerPolicyOut,
    BuyerPolicyUpdate,
    BuyerStateOut,
    ShoppingRequest,
)
from app.schemas.commerce import ShopResponse, VerifyPaymentRequest
from app.services import audit, ledger
from app.services.money import format_inr
from app.services.orchestrator import _intent_out, _transaction_out, run_shopping_flow

router = APIRouter(prefix="/buyer", tags=["buyer"])


def _policy_out(buyer: Buyer) -> BuyerPolicyOut:
    return BuyerPolicyOut(
        daily_budget=buyer.daily_budget,
        monthly_budget=buyer.monthly_budget,
        max_transaction=buyer.max_transaction,
        allowed_categories=list(buyer.allowed_categories or []),
        blocked_categories=list(buyer.blocked_categories or []),
        require_approval_above=buyer.require_approval_above,
        allow_automatic_purchase_below=buyer.allow_automatic_purchase_below,
        autonomy_level=AutonomyLevel(buyer.autonomy_level),
    )


@router.post("/shop", response_model=ShopResponse, summary="Run one bounded shopping flow")
def shop(
    request: ShoppingRequest,
    db: Session = Depends(get_db),
    buyer: Buyer = Depends(current_buyer),
) -> ShopResponse:
    return run_shopping_flow(db, request, buyer)


@router.get("/state", response_model=BuyerStateOut)
def get_state(
    db: Session = Depends(get_db), buyer: Buyer = Depends(current_buyer)
) -> BuyerStateOut:
    today = ledger.spent_today(db, buyer.id)
    month = ledger.spent_this_month(db, buyer.id)
    return BuyerStateOut(
        buyer_id=buyer.id,
        name=buyer.name,
        policy=_policy_out(buyer),
        spent_today=today,
        spent_this_month=month,
        remaining_today=max(buyer.daily_budget - today, 0),
        remaining_this_month=max(buyer.monthly_budget - month, 0),
        permissions_allowed=BUYER_AGENT_PERMISSIONS.allowed_names,
        permissions_denied=BUYER_AGENT_PERMISSIONS.denied_names,
    )


@router.put("/policy", response_model=BuyerPolicyOut, summary="Update buyer policy (human only)")
def update_policy(
    payload: BuyerPolicyUpdate,
    db: Session = Depends(get_db),
    buyer: Buyer = Depends(current_buyer),
    user: User = Depends(current_user),
) -> BuyerPolicyOut:
    """Policy is editable by its authenticated human owner only.

    Note what is NOT here: any agent-facing route to this handler. The buyer
    agent holds MODIFY_USER_POLICY in its DENIED set, and no agent code path
    reaches this endpoint - Security Principle 2. Authentication changes who
    may edit a policy; it does not give anyone a way to escape one.
    """
    changes = payload.model_dump(exclude_none=True)
    before = {field: getattr(buyer, field) for field in changes}
    for field, value in changes.items():
        setattr(buyer, field, value)
    db.commit()
    audit.record(
        db,
        agent_id=AgentId.HUMAN,
        action=AuditAction.POLICY_UPDATED,
        reason=(
            f"{user.name} <{user.email}> updated their policy: "
            f"{', '.join(changes) or 'no changes'}."
        ),
        input_reference={"before": before, "after": changes},
    )
    return _policy_out(buyer)


@router.post(
    "/verify-payment",
    response_model=ShopResponse,
    summary="Verify Razorpay payment signature and capture spend",
)
def verify_payment(
    payload: VerifyPaymentRequest,
    db: Session = Depends(get_db),
    buyer: Buyer = Depends(current_buyer),
) -> ShopResponse:
    txn = db.get(Transaction, payload.transaction_id)
    if txn is None or txn.buyer_id != buyer.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Transaction not found")

    intent = db.get(PurchaseIntent, txn.purchase_intent_id)
    if intent is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Purchase intent not found")

    # Idempotent return if already captured
    if txn.status == TransactionStatus.CAPTURED:
        return ShopResponse(
            status="completed",
            stage="payment",
            message=f"Payment captured. {format_inr(intent.amount)} paid to the merchant.",
            intent=_intent_out(intent),
            transaction=_transaction_out(txn),
            razorpay_called=True,
            razorpay_key_id=settings.razorpay_key_id if settings.razorpay_live_mode else None,
        )

    client = get_payment_client()
    is_valid = client.verify_payment(
        order_id=payload.razorpay_order_id,
        payment_id=payload.razorpay_payment_id,
        signature=payload.razorpay_signature,
    )

    if not is_valid:
        txn.status = TransactionStatus.FAILED
        txn.failure_reason = "Razorpay payment signature verification failed."
        intent.status = IntentStatus.FAILED
        db.commit()
        audit.record(
            db,
            agent_id=AgentId.RAZORPAY,
            action=AuditAction.INVALID_REQUEST,
            reason=(
                f"Signature verification failed for order {payload.razorpay_order_id}, "
                f"payment {payload.razorpay_payment_id}."
            ),
            purchase_intent_id=intent.id,
            status=AuditStatus.FAILED,
        )
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid payment signature.")

    txn.razorpay_order_id = payload.razorpay_order_id
    txn.razorpay_payment_id = payload.razorpay_payment_id
    txn.status = TransactionStatus.CAPTURED
    intent.status = IntentStatus.COMPLETED

    ledger.commit_spend(
        db,
        buyer_id=intent.buyer_id,
        purchase_intent_id=intent.id,
        amount=txn.amount,
    )
    db.commit()

    audit.record(
        db,
        agent_id=AgentId.RAZORPAY,
        action=AuditAction.PAYMENT_CONFIRMED,
        reason=(
            f"Payment {payload.razorpay_payment_id} captured and signature verified "
            f"for order {payload.razorpay_order_id}."
        ),
        purchase_intent_id=intent.id,
        output_reference={
            "order_id": payload.razorpay_order_id,
            "payment_id": payload.razorpay_payment_id,
            "amount": txn.amount,
        },
    )

    return ShopResponse(
        status="completed",
        stage="payment",
        message=f"Payment captured. {format_inr(intent.amount)} paid to the merchant.",
        intent=_intent_out(intent),
        transaction=_transaction_out(txn),
        razorpay_called=True,
        razorpay_key_id=settings.razorpay_key_id if settings.razorpay_live_mode else None,
    )

