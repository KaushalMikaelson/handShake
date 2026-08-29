"""Merchant dashboard endpoints (US-5b).

The merchant agent proposes opportunities; a human approves or rejects them.
Only APPROVED opportunities are eligible to be offered to a buyer, so nothing
the growth agent invents reaches a customer without sign-off.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_merchant
from app.database import get_db
from app.enums import (
    AgentId,
    AuditAction,
    IntentStatus,
    OpportunityStatus,
    TransactionStatus,
)
from app.models import BundleOpportunity, Merchant, Product, PurchaseIntent, Transaction
from app.schemas.catalog import BundleOpportunityOut, MerchantOut
from app.schemas.commerce import TrustOut
from app.services import audit
from app.trust import evaluate_trust

router = APIRouter(prefix="/merchant", tags=["merchant"])


@router.get("/profile", response_model=MerchantOut)
def profile(merchant: Merchant = Depends(current_merchant)) -> MerchantOut:
    return MerchantOut.model_validate(merchant)


@router.get("/opportunities", response_model=list[BundleOpportunityOut])
def opportunities(
    db: Session = Depends(get_db), merchant: Merchant = Depends(current_merchant)
) -> list[BundleOpportunityOut]:
    rows = list(
        db.scalars(
            select(BundleOpportunity)
            .where(BundleOpportunity.merchant_id == merchant.id)
            .order_by(BundleOpportunity.potential_aov_uplift.desc())
        )
    )
    names = {p.id: p.name for p in db.scalars(select(Product))}
    return [
        BundleOpportunityOut(
            id=o.id,
            merchant_id=o.merchant_id,
            anchor_product_id=o.anchor_product_id,
            companion_product_id=o.companion_product_id,
            anchor_name=names.get(o.anchor_product_id, ""),
            companion_name=names.get(o.companion_product_id, ""),
            potential_aov_uplift=o.potential_aov_uplift,
            rationale=o.rationale,
            status=o.status,
        )
        for o in rows
    ]


@router.post("/opportunities/{opportunity_id}/{decision}", response_model=BundleOpportunityOut)
def decide_opportunity(
    opportunity_id: str,
    decision: str,
    db: Session = Depends(get_db),
    merchant: Merchant = Depends(current_merchant),
) -> BundleOpportunityOut:
    if decision not in {"approve", "reject"}:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "decision must be approve or reject")
    opportunity = db.get(BundleOpportunity, opportunity_id)
    if opportunity is None or opportunity.merchant_id != merchant.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Opportunity not found")

    opportunity.status = (
        OpportunityStatus.APPROVED if decision == "approve" else OpportunityStatus.REJECTED
    )
    db.commit()
    audit.record(
        db,
        agent_id=AgentId.HUMAN,
        action=AuditAction.OFFER_GENERATED,
        reason=(
            f"Merchant {decision}d bundle opportunity {opportunity.anchor_product_id} -> "
            f"{opportunity.companion_product_id}."
        ),
        output_reference={"opportunity_id": opportunity.id, "status": opportunity.status},
    )
    names = {p.id: p.name for p in db.scalars(select(Product))}
    return BundleOpportunityOut(
        id=opportunity.id,
        merchant_id=opportunity.merchant_id,
        anchor_product_id=opportunity.anchor_product_id,
        companion_product_id=opportunity.companion_product_id,
        anchor_name=names.get(opportunity.anchor_product_id, ""),
        companion_name=names.get(opportunity.companion_product_id, ""),
        potential_aov_uplift=opportunity.potential_aov_uplift,
        rationale=opportunity.rationale,
        status=opportunity.status,
    )


@router.get("/metrics")
def metrics(db: Session = Depends(get_db), merchant: Merchant = Depends(current_merchant)):
    captured = list(
        db.scalars(
            select(Transaction).where(
                Transaction.merchant_id == merchant.id,
                Transaction.status == TransactionStatus.CAPTURED,
            )
        )
    )
    revenue = sum(t.amount for t in captured)
    blocked = db.scalars(
        select(PurchaseIntent).where(
            PurchaseIntent.merchant_id == merchant.id,
            PurchaseIntent.status == IntentStatus.POLICY_BLOCKED,
        )
    ).all()
    return {
        "merchant_id": merchant.id,
        "revenue": revenue,
        "orders_completed": len(captured),
        "average_order_value": revenue // len(captured) if captured else 0,
        "intents_blocked_by_policy": len(blocked),
        "max_discount_pct": merchant.max_discount_pct,
    }


@router.get("/trust", response_model=TrustOut)
def trust(
    db: Session = Depends(get_db), merchant: Merchant = Depends(current_merchant)
) -> TrustOut:
    products = list(db.scalars(select(Product).where(Product.merchant_id == merchant.id)))
    return TrustOut(**evaluate_trust(merchant, products).to_dict())
