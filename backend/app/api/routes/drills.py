"""Failure-mode drills (US-10) - the three scored failure paths, on demand.

These exist so the failure story can be demonstrated deterministically in a
five-minute judging window rather than hoping a real timeout occurs. Each drill
exercises the SAME production code path the real failure would, and none of
them weakens a control: the policy drill really is blocked by the real engine,
and the duplicate drill really does go through signature verification.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_buyer
from app.database import get_db
from app.models import Buyer, Transaction
from app.payments.razorpay_service import get_payment_client
from app.payments.webhook import handle_webhook
from app.schemas.agents import ShoppingRequest
from app.schemas.commerce import ShopResponse
from app.services.orchestrator import run_shopping_flow

router = APIRouter(prefix="/drills", tags=["failure-drills"])


@router.post("/policy-violation", response_model=ShopResponse, summary="Drill 1: policy block")
def drill_policy_violation(
    db: Session = Depends(get_db), buyer: Buyer = Depends(current_buyer)
) -> ShopResponse:
    """Attempt a purchase above max_transaction and confirm it never reaches Razorpay."""
    client = get_payment_client()
    before = client.call_count
    result = run_shopping_flow(
        db,
        ShoppingRequest(
            query=(
                "Buy me the best premium wireless headphones you have, budget up to "
                "Rs 20,000, I want the Sennheiser"
            )
        ),
        buyer,
    )
    result.razorpay_called = client.call_count > before
    return result


@router.post("/payment-timeout", response_model=ShopResponse, summary="Drill 2: unknown state")
def drill_payment_timeout(
    db: Session = Depends(get_db), buyer: Buyer = Depends(current_buyer)
) -> ShopResponse:
    """Force a gateway timeout and show the verify-don't-retry resolution path."""
    return run_shopping_flow(
        db,
        ShoppingRequest(
            query="Buy me a braided aux cable, budget Rs 1,000",
            simulate="payment_timeout",
        ),
        buyer,
    )


@router.post("/duplicate-webhook", summary="Drill 3: webhook replay")
def drill_duplicate_webhook(
    purchase_intent_id: str | None = None, db: Session = Depends(get_db)
):
    """Replay a signed webhook for an existing order and show it ignored once seen."""
    client = get_payment_client()
    stmt = select(Transaction).where(Transaction.razorpay_order_id.isnot(None))
    if purchase_intent_id:
        stmt = stmt.where(Transaction.purchase_intent_id == purchase_intent_id)
    txn = db.scalars(stmt.order_by(Transaction.created_at.desc())).first()
    if txn is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "No paid transaction to replay. Run a purchase first.",
        )

    order = client.fetch_order(txn.razorpay_order_id)
    event_id = f"evt_replay_{txn.id}"
    body, signature = client.build_webhook_payload(
        event_id=event_id,
        event="payment.captured",
        order=order,
        payment_id=txn.razorpay_payment_id or f"pay_replay_{txn.id}",
    )
    headers = {"x-razorpay-signature": signature, "x-razorpay-event-id": event_id}

    first = handle_webhook(db, body=body, headers=headers)
    second = handle_webhook(db, body=body, headers=headers)

    return {
        "purchase_intent_id": txn.purchase_intent_id,
        "event_id": event_id,
        "first_delivery": {"status": first.status, "duplicate": first.duplicate,
                           "detail": first.detail},
        "second_delivery": {"status": second.status, "duplicate": second.duplicate,
                            "detail": second.detail},
        "explanation": (
            "The second delivery lost the race on the unique constraint over "
            "processed_webhook_events.event_id, so it was logged as DUPLICATE_IGNORED. "
            "No second order completion and no second spend-ledger entry were written."
        ),
    }


@router.post("/tampered-webhook", summary="Drill 4: forged webhook signature")
def drill_tampered_webhook(db: Session = Depends(get_db)):
    """Send a webhook with a bad signature and show it rejected before parsing."""
    body = (
        b'{"event":"payment.captured","payload":{"payment":{"entity":'
        b'{"id":"pay_forged","order_id":"order_forged","amount":9999999,'
        b'"currency":"INR","status":"captured"}}}}'
    )
    result = handle_webhook(
        db,
        body=body,
        headers={"x-razorpay-signature": "not-a-valid-signature",
                 "x-razorpay-event-id": "evt_forged"},
    )
    return {
        "accepted": result.accepted,
        "status": result.status,
        "detail": result.detail,
        "explanation": (
            "Signature verification runs before the body is parsed, so a forged "
            "payload never reaches any state-changing code."
        ),
    }
