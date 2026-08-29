"""Buyer-facing endpoints: shop, policy, state."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import current_buyer
from app.database import get_db
from app.enums import AgentId, AuditAction, AutonomyLevel
from app.models import Buyer
from app.policies.permission import BUYER_AGENT_PERMISSIONS
from app.schemas.agents import (
    BuyerPolicyOut,
    BuyerPolicyUpdate,
    BuyerStateOut,
    ShoppingRequest,
)
from app.schemas.commerce import ShopResponse
from app.services import audit, ledger
from app.services.orchestrator import run_shopping_flow

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
) -> BuyerPolicyOut:
    """Policy is editable by the human owner only.

    Note what is NOT here: any agent-facing route to this handler. The buyer
    agent holds MODIFY_USER_POLICY in its DENIED set and no agent code path
    reaches this endpoint - Security Principle 2.
    """
    changes = payload.model_dump(exclude_none=True)
    for field, value in changes.items():
        setattr(buyer, field, value)
    db.commit()
    audit.record(
        db,
        agent_id=AgentId.HUMAN,
        action=AuditAction.POLICY_CHECK,
        reason=f"Buyer updated their own policy: {', '.join(changes) or 'no changes'}.",
        input_reference=changes,
    )
    return _policy_out(buyer)
