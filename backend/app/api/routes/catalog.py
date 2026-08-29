"""Agent-readable catalog endpoints (US-1).

FastAPI publishes the response schema at /openapi.json, which is the point: a
buyer agent reads the contract rather than scraping a page.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Merchant, Product
from app.schemas.catalog import CatalogResponse, MerchantOut, ProductOut

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("", response_model=CatalogResponse, summary="Machine-readable product catalog")
def get_catalog(
    db: Session = Depends(get_db),
    category: str | None = Query(default=None, description="Filter by category"),
    max_price: int | None = Query(default=None, description="Max unit price in paise"),
    in_stock_only: bool = Query(default=False),
) -> CatalogResponse:
    merchant = db.scalar(select(Merchant))
    if merchant is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No merchant configured")

    stmt = select(Product).where(Product.merchant_id == merchant.id)
    if category:
        stmt = stmt.where(Product.category == category)
    if max_price is not None:
        stmt = stmt.where(Product.price <= max_price)
    if in_stock_only:
        stmt = stmt.where(Product.stock_available.is_(True))

    products = list(db.scalars(stmt.order_by(Product.price.asc())))
    return CatalogResponse(
        merchant=MerchantOut.model_validate(merchant),
        count=len(products),
        products=[ProductOut.from_product(p) for p in products],
    )


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: str, db: Session = Depends(get_db)) -> ProductOut:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    return ProductOut.from_product(product)
