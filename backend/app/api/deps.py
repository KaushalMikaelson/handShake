"""Shared request dependencies.

Authentication is deliberately a hardcoded demo identity (PRD 3.12): building
multi-tenant auth would consume days and earns nothing against the rubric.
What matters is that AUTHORIZATION is a real, separate layer - the permission
system and policy engine - and it stays real regardless of how identity is
established here.
"""
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Buyer, Merchant


def current_buyer(
    db: Session = Depends(get_db),
    x_buyer_id: str | None = Header(default=None, alias="X-Buyer-Id"),
) -> Buyer:
    buyer = db.get(Buyer, x_buyer_id or settings.demo_buyer_id)
    if buyer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Buyer not found")
    return buyer


def current_merchant(
    db: Session = Depends(get_db),
    x_merchant_id: str | None = Header(default=None, alias="X-Merchant-Id"),
) -> Merchant:
    merchant = db.get(Merchant, x_merchant_id or settings.demo_merchant_id)
    if merchant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Merchant not found")
    return merchant
