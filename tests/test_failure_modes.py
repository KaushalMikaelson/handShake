"""The three scored failure modes (US-10), plus the forged-webhook case.

These are the tests that back the demo claims, so each asserts the *mechanism*,
not just the happy outcome: that Razorpay was never called, that no retry was
issued, that spend was counted exactly once.
"""
from app.enums import AuditAction, IntentStatus, TransactionStatus
from app.models import AuditEvent, SpendLedgerEntry, Transaction
from app.payments.webhook import handle_webhook
from app.schemas.agents import ShoppingRequest
from app.services.orchestrator import run_shopping_flow


def actions(db) -> list[str]:
    return [e.action for e in db.query(AuditEvent).order_by(AuditEvent.sequence).all()]


# =====================================================================
# Failure mode 1 - policy violation
# =====================================================================
def test_policy_violation_blocks_and_never_calls_razorpay(db, buyer, payments):
    """The core safety claim: a blocked intent must not reach the gateway."""
    payments.reset_counters()

    result = run_shopping_flow(
        db,
        ShoppingRequest(query="Buy premium Sennheiser wireless headphones, budget up to Rs 20,000"),
        buyer,
    )

    assert result.status == "blocked"
    assert result.policy.failed_rule == "budget.max_transaction"
    # The load-bearing assertion: zero calls on the payment client.
    assert payments.call_count == 0, f"Razorpay was called: {payments.calls}"
    assert result.razorpay_called is False
    assert db.query(Transaction).count() == 0
    assert AuditAction.POLICY_BLOCKED in actions(db)


def test_blocked_purchase_consumes_no_budget(db, buyer, payments):
    """A blocked attempt must not eat into the buyer's daily limit."""
    run_shopping_flow(
        db,
        ShoppingRequest(query="Buy premium Sennheiser wireless headphones, budget up to Rs 20,000"),
        buyer,
    )
    assert db.query(SpendLedgerEntry).count() == 0


def test_blocked_intent_is_recorded_with_its_reason(db, buyer, payments):
    """Blocking silently would be its own failure - the reason must be logged."""
    run_shopping_flow(
        db,
        ShoppingRequest(query="Buy premium Sennheiser wireless headphones, budget up to Rs 20,000"),
        buyer,
    )
    blocked = db.query(AuditEvent).filter(
        AuditEvent.action == AuditAction.POLICY_BLOCKED
    ).one()
    assert "exceeds the per-transaction limit" in blocked.reason
    assert blocked.policy_result["failed_rule"] == "budget.max_transaction"
    assert blocked.output_reference["razorpay_called"] is False


# =====================================================================
# Failure mode 2 - payment timeout / unknown state
# =====================================================================
def test_payment_timeout_verifies_instead_of_retrying(db, buyer, payments):
    payments.reset_counters()

    result = run_shopping_flow(
        db,
        ShoppingRequest(
            query="Buy me a braided aux cable for my headphones, budget Rs 1000",
            simulate="payment_timeout",
        ),
        buyer,
    )

    assert result.status == "pending_verification"
    assert result.transaction.status == TransactionStatus.PENDING_VERIFICATION

    # Exactly one create_order attempt: a retry would be the double-charge bug.
    assert payments.calls.count("create_order") == 1, payments.calls
    # ...and a verification lookup was made instead.
    assert "fetch_order_by_receipt" in payments.calls

    trail = actions(db)
    assert AuditAction.PAYMENT_TIMEOUT in trail
    assert AuditAction.PAYMENT_STATE_RESOLVED in trail


def test_timeout_commits_no_spend_while_state_is_unknown(db, buyer, payments):
    run_shopping_flow(
        db,
        ShoppingRequest(
            query="Buy me a braided aux cable for my headphones, budget Rs 1000",
            simulate="payment_timeout",
        ),
        buyer,
    )
    assert db.query(SpendLedgerEntry).count() == 0


def test_timeout_resolution_reconciles_an_order_that_actually_paid(db, buyer, payments):
    """If verification finds the order already paid, reconcile - never re-charge."""
    from app.services.orchestrator import execute_payment
    from app.models import PurchaseIntent

    result = run_shopping_flow(
        db,
        ShoppingRequest(
            query="Buy me a braided aux cable for my headphones, budget Rs 1000",
            simulate="payment_timeout",
        ),
        buyer,
    )
    intent = db.get(PurchaseIntent, result.intent.intent_id)
    txn = db.query(Transaction).filter(
        Transaction.purchase_intent_id == intent.id
    ).one()

    # The gateway completes the payment out-of-band, then we re-verify.
    payments.simulate_capture(txn.razorpay_order_id)
    payments.reset_counters()
    txn_out, status, _ = execute_payment(db, intent=intent, simulate="payment_timeout")

    assert status == "completed"
    assert txn_out.status == TransactionStatus.CAPTURED
    # Still exactly one order-creation attempt in this second pass.
    assert payments.calls.count("create_order") == 1
    assert db.query(SpendLedgerEntry).count() == 1


# =====================================================================
# Failure mode 3 - duplicate webhook delivery
# =====================================================================
def _signed(payments, order, payment_id, event_id):
    body, sig = payments.build_webhook_payload(
        event_id=event_id, event="payment.captured", order=order, payment_id=payment_id
    )
    return body, {"x-razorpay-signature": sig, "x-razorpay-event-id": event_id}


def test_duplicate_webhook_is_processed_exactly_once(db, buyer, payments):
    result = run_shopping_flow(
        db,
        ShoppingRequest(query="Buy me a braided aux cable for my headphones, budget Rs 1000"),
        buyer,
    )
    assert result.status == "completed"

    txn = db.query(Transaction).one()
    order = payments.fetch_order(txn.razorpay_order_id)
    body, headers = _signed(payments, order, txn.razorpay_payment_id, "evt_replay_1")

    first = handle_webhook(db, body=body, headers=headers)
    second = handle_webhook(db, body=body, headers=headers)
    third = handle_webhook(db, body=body, headers=headers)

    assert first.duplicate is False
    assert second.duplicate is True and second.status == "duplicate_ignored"
    assert third.duplicate is True
    # Both replays are "accepted" so the gateway stops retrying them.
    assert second.accepted is True

    assert AuditAction.DUPLICATE_WEBHOOK in actions(db)


def test_replayed_webhook_never_double_counts_spend(db, buyer, payments):
    """The financially load-bearing assertion for duplicate delivery."""
    result = run_shopping_flow(
        db,
        ShoppingRequest(query="Buy me a braided aux cable for my headphones, budget Rs 1000"),
        buyer,
    )
    amount = result.transaction.amount
    txn = db.query(Transaction).one()
    order = payments.fetch_order(txn.razorpay_order_id)

    for i in range(5):
        body, headers = _signed(payments, order, txn.razorpay_payment_id, f"evt_dup_{i}")
        handle_webhook(db, body=body, headers=headers)

    entries = db.query(SpendLedgerEntry).all()
    assert len(entries) == 1, "spend was committed more than once"
    assert entries[0].amount == amount


def test_distinct_event_ids_for_the_same_order_do_not_double_complete(db, buyer, payments):
    """Even with fresh event ids, an already-captured order must not re-apply."""
    run_shopping_flow(
        db,
        ShoppingRequest(query="Buy me a braided aux cable for my headphones, budget Rs 1000"),
        buyer,
    )
    txn = db.query(Transaction).one()
    order = payments.fetch_order(txn.razorpay_order_id)

    body, headers = _signed(payments, order, txn.razorpay_payment_id, "evt_fresh_id")
    result = handle_webhook(db, body=body, headers=headers)

    assert result.duplicate is False
    assert "already captured" in result.detail
    assert db.query(SpendLedgerEntry).count() == 1


# =====================================================================
# Failure mode 4 - forged webhook signature
# =====================================================================
def test_forged_signature_is_rejected_before_any_state_change(db, buyer, payments):
    run_shopping_flow(
        db,
        ShoppingRequest(query="Buy me a braided aux cable for my headphones, budget Rs 1000"),
        buyer,
    )
    before = db.query(SpendLedgerEntry).count()

    body = (
        b'{"event":"payment.captured","payload":{"payment":{"entity":'
        b'{"id":"pay_forged","order_id":"order_forged","amount":99999900,'
        b'"currency":"INR","status":"captured"}}}}'
    )
    result = handle_webhook(
        db, body=body,
        headers={"x-razorpay-signature": "bogus", "x-razorpay-event-id": "evt_forged"},
    )

    assert result.accepted is False
    assert result.status == "invalid_signature"
    assert db.query(SpendLedgerEntry).count() == before
    assert AuditAction.WEBHOOK_SIGNATURE_INVALID in actions(db)


def test_tampered_body_fails_verification(db, payments):
    """Changing one byte of an otherwise valid payload invalidates the HMAC."""
    order = {"id": "order_x", "amount": 10000, "currency": "INR"}
    body, sig = payments.build_webhook_payload(
        event_id="e1", event="payment.captured", order=order, payment_id="pay_x"
    )
    tampered = body.replace(b'"amount":10000', b'"amount":99999')
    assert payments.verify_webhook_signature(body=body, signature=sig) is True
    assert payments.verify_webhook_signature(body=tampered, signature=sig) is False


# =====================================================================
# Idempotency of order creation
# =====================================================================
def test_replaying_the_same_intent_does_not_create_a_second_order(db, buyer, payments):
    from app.services.orchestrator import execute_payment
    from app.models import PurchaseIntent

    result = run_shopping_flow(
        db,
        ShoppingRequest(query="Buy me a braided aux cable for my headphones, budget Rs 1000"),
        buyer,
    )
    intent = db.get(PurchaseIntent, result.intent.intent_id)
    first_order = db.query(Transaction).one().razorpay_order_id

    txn_out, status, _ = execute_payment(db, intent=intent)

    assert status == "completed"
    assert txn_out.razorpay_order_id == first_order
    assert db.query(Transaction).count() == 1
    assert db.query(SpendLedgerEntry).count() == 1
    assert intent.status == IntentStatus.COMPLETED
