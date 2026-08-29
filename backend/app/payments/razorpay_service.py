"""The ONLY module permitted to import the Razorpay SDK (US-8).

Everything else in the codebase talks to `RazorpayService`. That single
choke-point is what makes the safety claim testable: a test can count calls on
this object and assert the count is zero on any blocked path, and
`tests/test_architecture.py` greps the tree to prove no other module imports
the SDK behind its back.

Amounts arriving here are already catalog-sourced integer paise. This module
does no arithmetic on them beyond passing them through.

Simulator mode: with no RAZORPAY_KEY_ID/SECRET configured, a deterministic
in-process simulator stands in for the API - same method signatures, same
return shapes, same idempotency and signature semantics - so the entire
end-to-end flow, including the failure drills, runs with no credentials. Set
real test-mode keys and the identical code path talks to Razorpay.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
import uuid
from dataclasses import dataclass, field

from app.config import settings

logger = logging.getLogger(__name__)


class PaymentTimeout(Exception):
    """Raised when order creation/capture returns no definitive state.

    The correct response to this is NEVER a blind retry (Security Principle 6):
    the caller must move the transaction to PENDING_VERIFICATION and resolve the
    true state via fetch_order/fetch_payment.
    """


class PaymentError(Exception):
    pass


@dataclass
class _SimulatedOrder:
    id: str
    amount: int
    currency: str
    receipt: str
    status: str = "created"
    notes: dict = field(default_factory=dict)
    payment_id: str | None = None


class RazorpayService:
    """Facade over the Razorpay test-mode API, with a deterministic simulator."""

    def __init__(self) -> None:
        self._live = settings.razorpay_live_mode
        self._client = None
        # observability + test assertions: every outbound attempt is counted
        self.call_count = 0
        self.calls: list[str] = []
        self._orders: dict[str, _SimulatedOrder] = {}
        self._by_receipt: dict[str, str] = {}
        # demo hooks, set per-request by the failure simulator
        self._force_timeout = False
        self._force_failure = False

        if self._live:
            try:
                import razorpay

                self._client = razorpay.Client(
                    auth=(settings.razorpay_key_id, settings.razorpay_key_secret)
                )
                self._client.set_app_details({"title": "bounded-ai-commerce", "version": "1.0"})
            except Exception as exc:  # pragma: no cover - depends on env
                logger.warning("Razorpay SDK unavailable, using simulator: %s", exc)
                self._live = False

    # ------------------------------------------------------------------
    @property
    def live(self) -> bool:
        return self._live and self._client is not None

    @property
    def mode(self) -> str:
        return "razorpay_test" if self.live else "simulator"

    def arm_failure(self, mode: str | None) -> None:
        """Arm a one-shot failure for the next call (US-10 drills)."""
        self._force_timeout = mode == "payment_timeout"
        self._force_failure = mode == "payment_failed"

    def _record(self, method: str) -> None:
        self.call_count += 1
        self.calls.append(method)

    def reset_counters(self) -> None:
        self.call_count = 0
        self.calls = []

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------
    def create_order(
        self,
        *,
        amount: int,
        currency: str,
        idempotency_key: str,
        notes: dict | None = None,
    ) -> dict:
        """Create an order. `idempotency_key` is the receipt, so a retry of the
        same purchase intent returns the SAME order rather than a second charge.
        """
        self._record("create_order")

        if self._force_timeout:
            self._force_timeout = False
            # Model the genuinely dangerous case: the request DID reach the
            # gateway and an order exists, but we never saw the response. We
            # register the order (unless this receipt already has one - a
            # repeat attempt must never orphan the original) and then raise, so
            # the caller has something true to discover when it verifies.
            if idempotency_key not in self._by_receipt:
                order = _SimulatedOrder(
                    id=f"order_{uuid.uuid4().hex[:14]}",
                    amount=amount,
                    currency=currency,
                    receipt=idempotency_key,
                    status="created",
                    notes=notes or {},
                )
                self._orders[order.id] = order
                self._by_receipt[idempotency_key] = order.id
            raise PaymentTimeout(
                "No response from payment gateway within timeout; order state unknown."
            )

        if self._force_failure:
            self._force_failure = False
            raise PaymentError("Gateway declined the order creation request.")

        if self.live:  # pragma: no cover - requires credentials
            payload = {
                "amount": amount,
                "currency": currency,
                "receipt": idempotency_key,
                "notes": notes or {},
                "payment_capture": 1,
            }
            return dict(self._client.order.create(data=payload))

        # --- simulator ---
        existing_id = self._by_receipt.get(idempotency_key)
        if existing_id:
            return self._order_dict(self._orders[existing_id])
        order = _SimulatedOrder(
            id=f"order_{uuid.uuid4().hex[:14]}",
            amount=amount,
            currency=currency,
            receipt=idempotency_key,
            notes=notes or {},
        )
        self._orders[order.id] = order
        self._by_receipt[idempotency_key] = order.id
        return self._order_dict(order)

    def fetch_order(self, order_id: str) -> dict:
        """Authoritative state lookup - the correct response to an unknown state."""
        self._record("fetch_order")
        if self.live:  # pragma: no cover
            return dict(self._client.order.fetch(order_id))
        order = self._orders.get(order_id)
        if order is None:
            raise PaymentError(f"Unknown order {order_id}")
        return self._order_dict(order)

    def fetch_order_by_receipt(self, receipt: str) -> dict | None:
        """Resolve an order by our own idempotency key.

        Used when a timeout leaves us without an order id: we ask the gateway
        what actually happened rather than creating a second order.
        """
        self._record("fetch_order_by_receipt")
        if self.live:  # pragma: no cover
            orders = self._client.order.all({"receipt": receipt, "count": 1})
            items = orders.get("items", []) if isinstance(orders, dict) else []
            return dict(items[0]) if items else None
        order_id = self._by_receipt.get(receipt)
        return self._order_dict(self._orders[order_id]) if order_id else None

    def fetch_payment(self, payment_id: str) -> dict:
        self._record("fetch_payment")
        if self.live:  # pragma: no cover
            return dict(self._client.payment.fetch(payment_id))
        for order in self._orders.values():
            if order.payment_id == payment_id:
                return {
                    "id": payment_id,
                    "order_id": order.id,
                    "amount": order.amount,
                    "currency": order.currency,
                    "status": "captured" if order.status == "paid" else order.status,
                }
        raise PaymentError(f"Unknown payment {payment_id}")

    # ------------------------------------------------------------------
    # Capture (simulator only - live capture is driven by Razorpay Checkout)
    # ------------------------------------------------------------------
    def simulate_capture(self, order_id: str) -> dict:
        """Stand in for the shopper completing Checkout, in simulator mode."""
        if self.live:  # pragma: no cover
            raise PaymentError(
                "simulate_capture is unavailable in live mode; complete the payment "
                "through Razorpay Checkout instead."
            )
        order = self._orders.get(order_id)
        if order is None:
            raise PaymentError(f"Unknown order {order_id}")
        if order.status != "paid":
            order.status = "paid"
            order.payment_id = f"pay_{uuid.uuid4().hex[:14]}"
        return {
            "id": order.payment_id,
            "order_id": order.id,
            "amount": order.amount,
            "currency": order.currency,
            "status": "captured",
        }

    # ------------------------------------------------------------------
    # Signature verification (US-8) - implemented, never skipped
    # ------------------------------------------------------------------
    def verify_payment(
        self, *, order_id: str, payment_id: str, signature: str
    ) -> bool:
        """Verify a Checkout callback signature: HMAC-SHA256(order_id|payment_id)."""
        expected = hmac.new(
            (settings.razorpay_key_secret or settings.razorpay_webhook_secret).encode(),
            f"{order_id}|{payment_id}".encode(),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature or "")

    def verify_webhook_signature(self, *, body: bytes, signature: str) -> bool:
        """Verify the X-Razorpay-Signature header over the RAW request body.

        Verifying the raw bytes matters: re-serialising the JSON first would
        change whitespace and break the HMAC, which is a classic way teams end
        up "temporarily" disabling this check.
        """
        expected = hmac.new(
            settings.razorpay_webhook_secret.encode(), body, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature or "")

    def sign_webhook(self, body: bytes) -> str:
        """Produce a valid signature - used by the local replay script."""
        return hmac.new(
            settings.razorpay_webhook_secret.encode(), body, hashlib.sha256
        ).hexdigest()

    # ------------------------------------------------------------------
    def _order_dict(self, order: _SimulatedOrder) -> dict:
        return {
            "id": order.id,
            "entity": "order",
            "amount": order.amount,
            "amount_paid": order.amount if order.status == "paid" else 0,
            "amount_due": 0 if order.status == "paid" else order.amount,
            "currency": order.currency,
            "receipt": order.receipt,
            "status": order.status,
            "notes": order.notes,
            "created_at": int(time.time()),
        }

    def build_webhook_payload(
        self, *, event_id: str, event: str, order: dict, payment_id: str
    ) -> tuple[bytes, str]:
        """Build a signed webhook body for local replay drills (US-10.3)."""
        body = {
            "entity": "event",
            "event": event,
            "contains": ["payment"],
            "payload": {
                "payment": {
                    "entity": {
                        "id": payment_id,
                        "order_id": order["id"],
                        "amount": order["amount"],
                        "currency": order["currency"],
                        "status": "captured",
                    }
                }
            },
        }
        raw = json.dumps(body, separators=(",", ":")).encode()
        return raw, self.sign_webhook(raw)


_service: RazorpayService | None = None


def get_payment_client() -> RazorpayService:
    """Process-wide singleton so call counts and simulator state are shared."""
    global _service
    if _service is None:
        _service = RazorpayService()
    return _service
