"""The commerce pipeline (PRD 5.1).

Plain sequential Python, deliberately - the flow is linear (intent -> catalog ->
offer -> permission -> policy -> approval -> payment), not a branching graph, so
a workflow framework would add a dependency and a failure surface without
buying a single branch. See docs/architecture.md for the full reasoning.

Read this file top to bottom and the safety argument is visible in the control
flow itself: the agents run first and produce only *proposals*; the permission
check and policy engine sit between them and `_execute_payment`; and there is
exactly one call site for order creation, reachable only after both gates pass.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.agents.buyer import BuyerAgent
from app.agents.merchant import MerchantGrowthAgent
from app.enums import (
    AgentId,
    ApprovalStatus,
    AuditAction,
    AuditStatus,
    AutonomyLevel,
    IntentStatus,
    TransactionStatus,
)
from app.models import (
    ApprovalRequest,
    Buyer,
    Merchant,
    Product,
    PurchaseIntent,
    Transaction,
)
from app.payments.razorpay_service import PaymentError, PaymentTimeout, get_payment_client
from app.policies import (
    BuyerPolicy,
    Capability,
    MerchantPolicy,
    PermissionDenied,
    PolicyOutcome,
    ProposedBundle,
    ProposedPurchase,
    evaluate,
    require_capability,
)
from app.policies.permission import BUYER_AGENT_PERMISSIONS
from app.schemas.agents import BundleOffer, Recommendation, ShoppingRequest
from app.schemas.commerce import (
    ApprovalOut,
    PolicyDecisionOut,
    PurchaseIntentOut,
    ShopResponse,
    TransactionOut,
    TrustOut,
)
from app.services import audit, ledger
from app.services.money import format_inr
from app.trust import evaluate_trust

buyer_agent = BuyerAgent()
merchant_agent = MerchantGrowthAgent()


# ----------------------------------------------------------------------
# adapters: DB rows -> policy dataclasses
# ----------------------------------------------------------------------
def buyer_policy_of(buyer: Buyer) -> BuyerPolicy:
    return BuyerPolicy(
        daily_budget=buyer.daily_budget,
        monthly_budget=buyer.monthly_budget,
        max_transaction=buyer.max_transaction,
        allowed_categories=list(buyer.allowed_categories or []),
        blocked_categories=list(buyer.blocked_categories or []),
        require_approval_above=buyer.require_approval_above,
        allow_automatic_purchase_below=buyer.allow_automatic_purchase_below,
        autonomy_level=AutonomyLevel(buyer.autonomy_level),
    )


def merchant_policy_of(merchant: Merchant) -> MerchantPolicy:
    return MerchantPolicy(
        max_discount_pct=merchant.max_discount_pct,
        max_campaign_budget=merchant.max_campaign_budget,
        auto_approve_bundle_discount_below_pct=merchant.auto_approve_bundle_discount_below_pct,
    )


def _intent_out(intent: PurchaseIntent) -> PurchaseIntentOut:
    return PurchaseIntentOut(
        intent_id=intent.id,
        buyer_id=intent.buyer_id,
        merchant_id=intent.merchant_id,
        product_id=intent.product_id,
        amount=intent.amount,
        currency=intent.currency,
        reasoning=intent.reasoning,
        status=intent.status,
        created_at=intent.created_at,
    )


def _approval_out(approval: ApprovalRequest) -> ApprovalOut:
    return ApprovalOut(
        approval_id=approval.id,
        purchase_intent_id=approval.purchase_intent_id,
        buyer_id=approval.buyer_id,
        amount=approval.amount,
        status=approval.status,
        context=approval.context or {},
        created_at=approval.created_at,
        decided_at=approval.decided_at,
        decided_by=approval.decided_by,
    )


def _transaction_out(txn: Transaction) -> TransactionOut:
    return TransactionOut(
        id=txn.id,
        purchase_intent_id=txn.purchase_intent_id,
        amount=txn.amount,
        currency=txn.currency,
        status=txn.status,
        razorpay_order_id=txn.razorpay_order_id,
        razorpay_payment_id=txn.razorpay_payment_id,
        idempotency_key=txn.idempotency_key,
        failure_reason=txn.failure_reason,
    )


# ----------------------------------------------------------------------
# main pipeline
# ----------------------------------------------------------------------
def run_shopping_flow(db: Session, request: ShoppingRequest, buyer: Buyer) -> ShopResponse:
    merchant = db.scalar(select(Merchant))
    products = list(db.scalars(select(Product).where(Product.merchant_id == merchant.id)))

    # The intent id is allocated up front - before the agents run - purely so
    # that every event in this flow, including the ones emitted before the
    # PurchaseIntent row exists, lands on ONE timeline. Without this the audit
    # view would start at the policy check and lose the reasoning that led there.
    intent_id = f"pi_{uuid.uuid4().hex[:16]}"

    audit.record(
        db,
        agent_id=AgentId.HUMAN,
        action=AuditAction.USER_INTENT_RECEIVED,
        reason=f"Shopping request received: {request.query!r}",
        purchase_intent_id=intent_id,
        input_reference={"query": request.query, "buyer_id": buyer.id},
    )

    # --- 1. permission: may this agent even search and propose? (US-6c) ---
    try:
        require_capability(buyer_agent.agent_id, Capability.SEARCH_PRODUCTS)
        require_capability(buyer_agent.agent_id, Capability.COMPARE_PRODUCTS)
    except PermissionDenied as exc:
        audit.record(
            db,
            agent_id=AgentId.PERMISSION_SYSTEM,
            action=AuditAction.PERMISSION_DENIED,
            reason=str(exc),
            purchase_intent_id=intent_id,
            status=AuditStatus.DENIED,
        )
        return ShopResponse(
            status="permission_denied", stage="permission", message=str(exc)
        )

    # --- 2. parse the natural-language goal (US-2) ---
    parsed, parse_mode = buyer_agent.parse(request.query)
    if parsed.needs_clarification:
        audit.record(
            db,
            agent_id=AgentId.BUYER_AGENT,
            action=AuditAction.INTENT_CLARIFICATION_REQUESTED,
            reason=parsed.clarification_question or "Budget not specified.",
            purchase_intent_id=intent_id,
            status=AuditStatus.PENDING,
            output_reference=parsed.model_dump(),
        )
        return ShopResponse(
            status="needs_clarification",
            stage="intent",
            message=parsed.clarification_question
            or "I need a budget before I can shop for this.",
            needs_clarification=True,
            clarification_question=parsed.clarification_question,
            parsed_intent=parsed.model_dump(),
        )

    audit.record(
        db,
        agent_id=AgentId.BUYER_AGENT,
        action=AuditAction.CATALOG_SEARCH,
        reason=(
            f"Parsed intent via {parse_mode} path; querying catalog for category "
            f"{parsed.category!r} under {format_inr(parsed.budget_max or 0)}."
        ),
        purchase_intent_id=intent_id,
        input_reference=parsed.model_dump(),
        output_reference={"candidates_found": len(products)},
    )

    # --- 3. rank and justify (US-3) ---
    recommendation: Recommendation = buyer_agent.recommend(products, parsed)
    if recommendation.selected_product_id is None:
        audit.record(
            db,
            agent_id=AgentId.BUYER_AGENT,
            action=AuditAction.PRODUCT_SELECTED,
            reason=recommendation.justification,
            purchase_intent_id=intent_id,
            status=AuditStatus.FAILED,
            output_reference={"candidates": [c.model_dump() for c in recommendation.candidates]},
        )
        return ShopResponse(
            status="no_match",
            stage="recommendation",
            message=recommendation.justification,
            parsed_intent=parsed.model_dump(),
            recommendation=recommendation,
        )

    product = db.get(Product, recommendation.selected_product_id)
    audit.record(
        db,
        agent_id=AgentId.BUYER_AGENT,
        action=AuditAction.PRODUCT_SELECTED,
        reason=recommendation.justification,
        purchase_intent_id=intent_id,
        input_reference={"llm_mode": recommendation.llm_mode},
        output_reference={
            "product_id": product.id,
            "amount": product.price,
            "candidates": [c.model_dump() for c in recommendation.candidates],
        },
    )

    # --- 4. merchant growth agent proposes (or declines) a bundle (US-5) ---
    bundle: BundleOffer = merchant_agent.propose_bundle(
        db, merchant, product, recommendation.remaining_budget
    )
    audit.record(
        db,
        agent_id=AgentId.MERCHANT_AGENT,
        action=AuditAction.OFFER_GENERATED if bundle.offered else AuditAction.NO_BUNDLE_OFFERED,
        reason=bundle.reasoning,
        purchase_intent_id=intent_id,
        output_reference=bundle.model_dump(),
        status=AuditStatus.OK,
    )

    # --- 5. trust: advisory only (US-11) ---
    trust_report = evaluate_trust(merchant, products)
    audit.record(
        db,
        agent_id=AgentId.TRUST_ENGINE,
        action=AuditAction.TRUST_EVALUATED,
        reason=(
            f"Merchant trust {trust_report.score}/100 ({trust_report.band}). "
            f"Advisory only - cannot override any policy rule."
        ),
        purchase_intent_id=intent_id,
        output_reference=trust_report.to_dict(),
    )
    trust_out = TrustOut(**trust_report.to_dict())

    # --- 6. decide what is actually being charged ---
    # The amount is re-read from the catalog row, never taken from model output.
    charge_amount = product.price
    proposed_bundle = None
    if bundle.offered and bundle.bundle_price is not None:
        proposed_bundle = ProposedBundle(
            discount_pct=bundle.discount_pct,
            bundle_price=bundle.bundle_price,
            list_price=bundle.list_price or 0,
        )
        if request.accept_bundle:
            charge_amount = bundle.bundle_price

    # --- 7. create the PurchaseIntent: a request, not an action (US-4) ---
    try:
        require_capability(buyer_agent.agent_id, Capability.CREATE_PURCHASE_INTENT)
    except PermissionDenied as exc:
        audit.record(
            db,
            agent_id=AgentId.PERMISSION_SYSTEM,
            action=AuditAction.PERMISSION_DENIED,
            reason=str(exc),
            purchase_intent_id=intent_id,
            status=AuditStatus.DENIED,
        )
        return ShopResponse(status="permission_denied", stage="permission", message=str(exc))

    intent = PurchaseIntent(
        id=intent_id,
        buyer_id=buyer.id,
        merchant_id=merchant.id,
        product_id=product.id,
        amount=charge_amount,
        currency=product.currency,
        reasoning=recommendation.justification,
        parsed_intent=parsed.model_dump(),
        evaluation={
            "recommendation": recommendation.model_dump(),
            "candidates": [c.model_dump() for c in recommendation.candidates],
        },
        bundle=bundle.model_dump(),
        trust=trust_report.to_dict(),
        status=IntentStatus.CREATED,
    )
    db.add(intent)
    db.commit()

    audit.record(
        db,
        agent_id=AgentId.PERMISSION_SYSTEM,
        action=AuditAction.PERMISSION_CHECK,
        reason=(
            f"Buyer agent holds CREATE_PURCHASE_INTENT. Denied capabilities remain "
            f"{', '.join(BUYER_AGENT_PERMISSIONS.denied_names)}."
        ),
        purchase_intent_id=intent.id,
        output_reference={
            "allowed": BUYER_AGENT_PERMISSIONS.allowed_names,
            "denied": BUYER_AGENT_PERMISSIONS.denied_names,
        },
    )

    # --- 8. the deterministic gate (US-6) ---
    return _apply_policy_and_proceed(
        db,
        buyer=buyer,
        merchant=merchant,
        intent=intent,
        product=product,
        recommendation=recommendation,
        bundle=bundle,
        proposed_bundle=proposed_bundle,
        parsed=parsed,
        trust_out=trust_out,
        simulate=request.simulate,
    )


def _apply_policy_and_proceed(
    db: Session,
    *,
    buyer: Buyer,
    merchant: Merchant,
    intent: PurchaseIntent,
    product: Product,
    recommendation: Recommendation,
    bundle: BundleOffer,
    proposed_bundle: ProposedBundle | None,
    parsed,
    trust_out: TrustOut,
    simulate: str | None,
) -> ShopResponse:
    policy = buyer_policy_of(buyer)
    merchant_policy = merchant_policy_of(merchant)
    context = ledger.policy_context(db, buyer.id)

    decision = evaluate(
        ProposedPurchase(
            amount=intent.amount,
            category=product.category,
            product_id=product.id,
            merchant_id=merchant.id,
            bundle=proposed_bundle,
        ),
        policy,
        merchant_policy,
        context,
    )
    intent.policy_result = decision.to_dict()
    policy_out = PolicyDecisionOut(**decision.to_dict())

    common = dict(
        parsed_intent=parsed.model_dump(),
        recommendation=recommendation,
        bundle=bundle,
        trust=trust_out,
        policy=policy_out,
    )

    # --- BLOCKED: Razorpay is never called on this path ---
    if not decision.allowed and decision.outcome == PolicyOutcome.BLOCKED:
        intent.status = IntentStatus.POLICY_BLOCKED
        db.commit()
        audit.record(
            db,
            agent_id=AgentId.POLICY_ENGINE,
            action=AuditAction.POLICY_BLOCKED,
            reason=decision.reason,
            purchase_intent_id=intent.id,
            policy_result=decision.to_dict(),
            status=AuditStatus.BLOCKED,
            output_reference={
                "failed_rule": decision.failed_rule,
                "razorpay_called": False,
            },
        )
        return ShopResponse(
            status="blocked",
            stage="policy",
            message=f"Blocked by rule '{decision.failed_rule}': {decision.reason}",
            intent=_intent_out(intent),
            razorpay_called=False,
            **common,
        )

    audit.record(
        db,
        agent_id=AgentId.POLICY_ENGINE,
        action=AuditAction.POLICY_CHECK,
        reason=decision.reason,
        purchase_intent_id=intent.id,
        policy_result=decision.to_dict(),
        status=AuditStatus.OK,
    )

    # --- Level 1: recommendation only, no intent may proceed ---
    if decision.outcome == PolicyOutcome.RECOMMEND_ONLY:
        intent.status = IntentStatus.RECOMMENDATION_ONLY
        db.commit()
        return ShopResponse(
            status="recommendation_only",
            stage="autonomy",
            message=decision.reason,
            intent=_intent_out(intent),
            razorpay_called=False,
            **common,
        )

    # --- human approval gate (US-7) ---
    if decision.requires_human_approval:
        require_capability(buyer_agent.agent_id, Capability.REQUEST_APPROVAL)
        approval = ApprovalRequest(
            id=f"apr_{uuid.uuid4().hex[:12]}",
            purchase_intent_id=intent.id,
            buyer_id=buyer.id,
            amount=intent.amount,
            context={
                "product": {
                    "product_id": product.id,
                    "name": product.name,
                    "brand": product.brand,
                    "price": product.price,
                },
                "merchant": {"id": merchant.id, "name": merchant.name},
                "amount": intent.amount,
                "spent_today": context.spent_today,
                "remaining_after_purchase": (
                    policy.daily_budget - context.spent_today - intent.amount
                ),
                "policy": decision.to_dict(),
                "agent_reasoning": recommendation.justification,
                "bundle": bundle.model_dump(),
                "trust": trust_out.model_dump(),
            },
            status=ApprovalStatus.PENDING,
        )
        db.add(approval)
        intent.status = IntentStatus.AWAITING_APPROVAL
        db.commit()
        audit.record(
            db,
            agent_id=AgentId.BUYER_AGENT,
            action=AuditAction.APPROVAL_REQUESTED,
            reason=decision.reason,
            purchase_intent_id=intent.id,
            policy_result=decision.to_dict(),
            status=AuditStatus.PENDING,
            output_reference={"approval_id": approval.id, "amount": intent.amount},
        )
        return ShopResponse(
            status="awaiting_approval",
            stage="approval",
            message=decision.reason,
            intent=_intent_out(intent),
            approval=_approval_out(approval),
            razorpay_called=False,
            **common,
        )

    # --- Level 3 bounded auto-purchase ---
    intent.status = IntentStatus.AUTO_AUTHORIZED
    db.commit()
    audit.record(
        db,
        agent_id=AgentId.POLICY_ENGINE,
        action=AuditAction.AUTO_AUTHORIZED,
        reason=decision.reason,
        purchase_intent_id=intent.id,
        policy_result=decision.to_dict(),
    )
    txn_out, txn_status, message = execute_payment(db, intent=intent, simulate=simulate)
    return ShopResponse(
        status=txn_status,
        stage="payment",
        message=message,
        intent=_intent_out(intent),
        transaction=txn_out,
        razorpay_called=True,
        razorpay_key_id=settings.razorpay_key_id if settings.razorpay_live_mode else None,
        **common,
    )


# ----------------------------------------------------------------------
# payment execution - the ONLY path that reaches the gateway
# ----------------------------------------------------------------------
def execute_payment(
    db: Session, *, intent: PurchaseIntent, simulate: str | None = None
) -> tuple[TransactionOut | None, str, str]:
    """Create (and in simulator mode, capture) the order for an authorised intent.

    Reachable only from a policy verdict of AUTO_APPROVE, or from a human
    pressing Approve. Both callers have already passed the permission check.
    """
    require_capability(buyer_agent.agent_id, Capability.CREATE_PAYMENT)
    client = get_payment_client()

    # Idempotency key derived from the intent id: retrying the same intent can
    # never produce a second order (US-8).
    idempotency_key = f"intent_{intent.id}"

    existing = db.scalar(
        select(Transaction).where(Transaction.idempotency_key == idempotency_key)
    )
    if existing is not None and existing.status == TransactionStatus.CAPTURED:
        return (
            _transaction_out(existing),
            "completed",
            "This purchase intent was already paid; returning the existing transaction.",
        )

    txn = existing or Transaction(
        id=f"txn_{uuid.uuid4().hex[:14]}",
        purchase_intent_id=intent.id,
        buyer_id=intent.buyer_id,
        merchant_id=intent.merchant_id,
        amount=intent.amount,
        currency=intent.currency,
        idempotency_key=idempotency_key,
        status=TransactionStatus.CREATED,
    )
    if existing is None:
        db.add(txn)
        db.flush()

    if simulate:
        client.arm_failure(simulate)

    # --- create order ---
    try:
        order = client.create_order(
            amount=intent.amount,
            currency=intent.currency,
            idempotency_key=idempotency_key,
            notes={
                "purchase_intent_id": intent.id,
                "buyer_id": intent.buyer_id,
                "product_id": intent.product_id,
            },
        )
    except PaymentTimeout as exc:
        return _handle_timeout(db, intent=intent, txn=txn, client=client,
                               idempotency_key=idempotency_key, error=str(exc))
    except PaymentError as exc:
        txn.status = TransactionStatus.FAILED
        txn.failure_reason = str(exc)
        intent.status = IntentStatus.FAILED
        db.commit()
        audit.record(
            db,
            agent_id=AgentId.RAZORPAY,
            action=AuditAction.INVALID_REQUEST,
            reason=f"Order creation failed: {exc}. No money moved; no retry attempted.",
            purchase_intent_id=intent.id,
            status=AuditStatus.FAILED,
        )
        return _transaction_out(txn), "failed", f"Payment could not be initiated: {exc}"

    txn.razorpay_order_id = order["id"]
    txn.status = TransactionStatus.AUTHORIZED
    intent.status = IntentStatus.ORDER_CREATED
    db.commit()
    audit.record(
        db,
        agent_id=AgentId.RAZORPAY,
        action=AuditAction.RAZORPAY_ORDER_CREATED,
        reason=(
            f"Order {order['id']} created for {format_inr(intent.amount)} "
            f"(idempotency key {idempotency_key}, mode {client.mode})."
        ),
        purchase_intent_id=intent.id,
        input_reference={"amount": intent.amount, "idempotency_key": idempotency_key},
        output_reference={"order_id": order["id"], "status": order["status"]},
    )

    # In live test mode the shopper completes Checkout and Razorpay sends the
    # webhook; there is nothing further to do here.
    if client.live:  # pragma: no cover - requires credentials
        return (
            _transaction_out(txn),
            "order_created",
            f"Razorpay order {order['id']} created. Awaiting checkout completion.",
        )

    # Simulator: stand in for the shopper completing Checkout, then let the
    # webhook path (signature-verified, deduplicated) do the state change.
    payment = client.simulate_capture(order["id"])
    audit.record(
        db,
        agent_id=AgentId.RAZORPAY,
        action=AuditAction.PAYMENT_CONFIRMED,
        reason=f"Payment {payment['id']} captured for order {order['id']}.",
        purchase_intent_id=intent.id,
        output_reference=payment,
    )

    from app.payments.webhook import handle_webhook

    body, signature = client.build_webhook_payload(
        event_id=f"evt_sim_{txn.id}",
        event="payment.captured",
        order=order,
        payment_id=payment["id"],
    )
    handle_webhook(
        db,
        body=body,
        headers={
            "x-razorpay-signature": signature,
            "x-razorpay-event-id": f"evt_sim_{txn.id}",
        },
    )
    db.refresh(txn)
    return (
        _transaction_out(txn),
        "completed",
        f"Payment captured. {format_inr(intent.amount)} paid to the merchant.",
    )


def _handle_timeout(
    db: Session, *, intent: PurchaseIntent, txn: Transaction, client, idempotency_key: str,
    error: str,
) -> tuple[TransactionOut, str, str]:
    """US-10.2 - unknown payment state. Verify; never blindly retry.

    A retry here is the single most expensive mistake available to this system:
    if the first call did reach the gateway, retrying double-charges the buyer.
    So we ask the gateway what actually happened, using our own idempotency key
    as the lookup, and record whichever answer comes back.
    """
    txn.status = TransactionStatus.PENDING_VERIFICATION
    intent.status = IntentStatus.PENDING_VERIFICATION
    txn.failure_reason = error
    db.commit()

    audit.record(
        db,
        agent_id=AgentId.RAZORPAY,
        action=AuditAction.PAYMENT_TIMEOUT,
        reason=(
            f"{error} Transaction moved to PENDING_VERIFICATION. "
            f"No retry issued - resolving true state via the gateway instead."
        ),
        purchase_intent_id=intent.id,
        status=AuditStatus.PENDING,
        input_reference={"idempotency_key": idempotency_key},
    )

    resolved = client.fetch_order_by_receipt(idempotency_key)

    if resolved is None:
        # The gateway never saw it, so no money moved and it is safe to say so.
        txn.status = TransactionStatus.FAILED
        txn.failure_reason = "Timed out; gateway has no record of the order."
        intent.status = IntentStatus.FAILED
        db.commit()
        audit.record(
            db,
            agent_id=AgentId.RAZORPAY,
            action=AuditAction.PAYMENT_STATE_RESOLVED,
            reason=(
                "Verification found no order at the gateway for this idempotency key: "
                "no money moved. Marked FAILED; the buyer may safely retry."
            ),
            purchase_intent_id=intent.id,
            status=AuditStatus.FAILED,
        )
        return (
            _transaction_out(txn),
            "failed",
            "Payment timed out and the gateway has no record of it. Nothing was charged.",
        )

    txn.razorpay_order_id = resolved["id"]
    gateway_status = resolved.get("status")

    if gateway_status == "paid":
        txn.status = TransactionStatus.CAPTURED
        intent.status = IntentStatus.COMPLETED
        ledger.commit_spend(
            db, buyer_id=intent.buyer_id, purchase_intent_id=intent.id, amount=txn.amount
        )
        db.commit()
        audit.record(
            db,
            agent_id=AgentId.RAZORPAY,
            action=AuditAction.PAYMENT_STATE_RESOLVED,
            reason=(
                f"Verification found order {resolved['id']} already PAID. Reconciled "
                f"locally instead of retrying - a retry here would have double-charged."
            ),
            purchase_intent_id=intent.id,
            output_reference=resolved,
        )
        return (
            _transaction_out(txn),
            "completed",
            "Payment had actually succeeded; state reconciled without a second charge.",
        )

    # Order exists but is unpaid: still no blind retry. Leave it pending and
    # let the webhook or a later verification settle it.
    txn.status = TransactionStatus.PENDING_VERIFICATION
    txn.failure_reason = f"Gateway reports order status '{gateway_status}'."
    db.commit()
    audit.record(
        db,
        agent_id=AgentId.RAZORPAY,
        action=AuditAction.PAYMENT_STATE_RESOLVED,
        reason=(
            f"Verification found order {resolved['id']} in state '{gateway_status}'. "
            f"Held as PENDING_VERIFICATION; no retry and no spend committed."
        ),
        purchase_intent_id=intent.id,
        status=AuditStatus.PENDING,
        output_reference=resolved,
    )
    return (
        _transaction_out(txn),
        "pending_verification",
        f"Payment state is unresolved (gateway says '{gateway_status}'). "
        f"Held for verification rather than retried.",
    )


def _purchase_context_out(db: Session, intent: PurchaseIntent) -> dict:
    """Rehydrate the shopping context attached to a completed payment response."""
    return {
        "parsed_intent": intent.parsed_intent or None,
        "recommendation": _recommendation_from_intent(db, intent),
        "bundle": BundleOffer(**intent.bundle) if intent.bundle else None,
        "trust": TrustOut(**intent.trust) if intent.trust else None,
        "policy": (
            PolicyDecisionOut(**intent.policy_result)
            if intent.policy_result
            else None
        ),
    }


def _recommendation_from_intent(db: Session, intent: PurchaseIntent) -> Recommendation | None:
    evaluation = intent.evaluation or {}
    stored = evaluation.get("recommendation")
    if stored:
        return Recommendation(**stored)

    candidates = evaluation.get("candidates") or []
    product = db.get(Product, intent.product_id)
    product_price = product.price if product is not None else intent.amount
    budget_max = (intent.parsed_intent or {}).get("budget_max")
    remaining_budget = (
        max(budget_max - product_price, 0)
        if isinstance(budget_max, int)
        else None
    )

    return Recommendation(
        selected_product_id=intent.product_id,
        selected_name=product.name if product is not None else None,
        amount=product_price,
        remaining_budget=remaining_budget,
        justification=intent.reasoning,
        candidates=candidates,
        llm_mode=evaluation.get("llm_mode", "deterministic"),
    )
