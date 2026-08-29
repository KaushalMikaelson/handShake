"""Webhook ingestion (US-8, US-10.3).

Ordering here is deliberate and is the whole correctness story:

  1. Verify the signature over the RAW body. An unverified body is never parsed
     into a state change.
  2. Claim the event_id by INSERTing into processed_webhook_events. The DB's
     uniqueness constraint - not an `if already_seen` check - is what makes this
     safe: two concurrent deliveries race on the insert and exactly one wins.
  3. Only the winner applies the side effect (completing the order, committing
     spend). The loser is logged as DUPLICATE_IGNORED and returns 200, because
     a duplicate is a successfully-handled delivery, not an error to retry.

That ordering is why a replayed webhook cannot double-complete an order or
double-count a buyer's budget.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.enums import (
    AgentId,
    AuditAction,
    AuditStatus,
    IntentStatus,
    TransactionStatus,
)
from app.models import Merchant, ProcessedWebhookEvent, PurchaseIntent, Transaction
from app.payments.razorpay_service import get_payment_client
from app.services import audit, ledger


@dataclass
class WebhookResult:
    accepted: bool
    duplicate: bool
    status: str
    detail: str
    purchase_intent_id: str | None = None


def _digest(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _extract_event_id(headers: dict, payload: dict) -> str:
    """Razorpay sends x-razorpay-event-id; fall back to a payload-derived id."""
    header_id = headers.get("x-razorpay-event-id") or headers.get("X-Razorpay-Event-Id")
    if header_id:
        return str(header_id)
    entity = (
        payload.get("payload", {}).get("payment", {}).get("entity", {})
        or payload.get("payload", {}).get("order", {}).get("entity", {})
    )
    return f"{payload.get('event', 'unknown')}:{entity.get('id', 'unknown')}"


def handle_webhook(db: Session, *, body: bytes, headers: dict) -> WebhookResult:
    client = get_payment_client()
    signature = headers.get("x-razorpay-signature") or headers.get("X-Razorpay-Signature") or ""

    # --- 1. signature first, always ---
    if not client.verify_webhook_signature(body=body, signature=signature):
        audit.record(
            db,
            agent_id=AgentId.RAZORPAY,
            action=AuditAction.WEBHOOK_SIGNATURE_INVALID,
            reason="Webhook rejected: signature did not match the raw request body.",
            status=AuditStatus.FAILED,
            input_reference={"digest": _digest(body)},
        )
        return WebhookResult(
            accepted=False,
            duplicate=False,
            status="invalid_signature",
            detail="Webhook signature verification failed.",
        )

    try:
        payload = json.loads(body.decode())
    except (ValueError, UnicodeDecodeError):
        audit.record(
            db,
            agent_id=AgentId.RAZORPAY,
            action=AuditAction.INVALID_REQUEST,
            reason="Webhook body was not valid JSON.",
            status=AuditStatus.FAILED,
        )
        return WebhookResult(
            accepted=False, duplicate=False, status="invalid_payload",
            detail="Webhook body was not valid JSON.",
        )

    event_id = _extract_event_id(headers, payload)
    event_type = str(payload.get("event", ""))
    entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
    order_id = entity.get("order_id")
    payment_id = entity.get("id")

    transaction = (
        db.scalar(select(Transaction).where(Transaction.razorpay_order_id == order_id))
        if order_id
        else None
    )
    intent_id = transaction.purchase_intent_id if transaction else None

    # --- 2. claim the event id; the DB constraint arbitrates ---
    record = ProcessedWebhookEvent(
        event_id=event_id,
        event_type=event_type,
        purchase_intent_id=intent_id,
        payload_digest=_digest(body),
        processed_at=datetime.now(timezone.utc),
    )
    db.add(record)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        audit.record(
            db,
            agent_id=AgentId.RAZORPAY,
            action=AuditAction.DUPLICATE_WEBHOOK,
            reason=(
                f"Webhook {event_id} was already processed; ignoring this replay. "
                f"No order completion or spend entry was applied a second time."
            ),
            purchase_intent_id=intent_id,
            status=AuditStatus.IGNORED,
            input_reference={"event_id": event_id, "event": event_type},
        )
        return WebhookResult(
            accepted=True,
            duplicate=True,
            status="duplicate_ignored",
            detail=f"Duplicate webhook {event_id} ignored.",
            purchase_intent_id=intent_id,
        )

    # --- 3. sole winner applies the side effect ---
    if transaction is None:
        db.commit()
        audit.record(
            db,
            agent_id=AgentId.RAZORPAY,
            action=AuditAction.WEBHOOK_PROCESSED,
            reason=f"Webhook {event_id} accepted but no local transaction matches "
                   f"order {order_id}.",
            status=AuditStatus.OK,
            input_reference={"event_id": event_id, "order_id": order_id},
        )
        return WebhookResult(
            accepted=True, duplicate=False, status="no_matching_transaction",
            detail=f"No local transaction for order {order_id}.",
        )

    applied = _apply_payment_event(
        db, transaction=transaction, event_type=event_type, payment_id=payment_id
    )
    db.commit()

    audit.record(
        db,
        agent_id=AgentId.RAZORPAY,
        action=AuditAction.WEBHOOK_PROCESSED,
        reason=f"Webhook {event_id} ({event_type}) processed: {applied}.",
        purchase_intent_id=intent_id,
        input_reference={"event_id": event_id, "event": event_type, "order_id": order_id},
        output_reference={"payment_id": payment_id, "transaction_status": transaction.status},
        status=AuditStatus.OK,
    )
    return WebhookResult(
        accepted=True,
        duplicate=False,
        status="processed",
        detail=applied,
        purchase_intent_id=intent_id,
    )


def _apply_payment_event(
    db: Session, *, transaction: Transaction, event_type: str, payment_id: str | None
) -> str:
    intent = db.get(PurchaseIntent, transaction.purchase_intent_id)

    if event_type in {"payment.captured", "order.paid"}:
        if transaction.status == TransactionStatus.CAPTURED:
            return "transaction was already captured; no change applied"
        transaction.status = TransactionStatus.CAPTURED
        transaction.razorpay_payment_id = payment_id or transaction.razorpay_payment_id
        if intent is not None:
            intent.status = IntentStatus.COMPLETED
            ledger.commit_spend(
                db,
                buyer_id=intent.buyer_id,
                purchase_intent_id=intent.id,
                amount=transaction.amount,
            )
            merchant = db.get(Merchant, intent.merchant_id)
            if merchant is not None:
                merchant.successful_transactions += 1
        audit.record(
            db,
            agent_id=AgentId.SYSTEM,
            action=AuditAction.ORDER_COMPLETED,
            reason=(
                f"Order {transaction.razorpay_order_id} completed and "
                f"{transaction.amount} paise committed to the buyer's spend ledger."
            ),
            purchase_intent_id=transaction.purchase_intent_id,
            status=AuditStatus.OK,
            commit=False,
        )
        return "order completed and spend committed"

    if event_type in {"payment.failed"}:
        transaction.status = TransactionStatus.FAILED
        transaction.failure_reason = "Gateway reported payment.failed"
        if intent is not None:
            intent.status = IntentStatus.FAILED
            merchant = db.get(Merchant, intent.merchant_id)
            if merchant is not None:
                merchant.failed_transactions += 1
        return "transaction marked failed; no spend committed"

    return f"event '{event_type}' recorded with no state change"
