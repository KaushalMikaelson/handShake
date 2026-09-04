"""Agent-readable catalog contract (US-1).

Field names and types here are the machine contract a Buyer Agent codes
against; FastAPI publishes them as OpenAPI at /openapi.json so the agent's
parser is never coupled to field order or HTML layout.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:  # pragma: no cover
    from app.models import Product


class ProductOut(BaseModel):
    product_id: str
    name: str
    brand: str
    price: int = Field(description="Unit price in paise (integer). 899900 = Rs 8,999.00")
    currency: str
    category: str
    stock_available: bool
    attributes: list[str]
    bundle_eligible: bool
    max_discount_pct: int
    companion_product_ids: list[str] = Field(default_factory=list)

    @classmethod
    def from_product(cls, product: "Product") -> "ProductOut":
        return cls(
            product_id=product.id,
            name=product.name,
            brand=product.brand,
            price=product.price,
            currency=product.currency,
            category=product.category,
            stock_available=product.stock_available,
            attributes=list(product.attributes or []),
            bundle_eligible=product.bundle_eligible,
            max_discount_pct=product.max_discount_pct,
            companion_product_ids=list(product.companion_product_ids or []),
        )


class MerchantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    max_discount_pct: int
    max_campaign_budget: int
    auto_approve_bundle_discount_below_pct: int


class CatalogResponse(BaseModel):
    merchant: MerchantOut
    currency: str = "INR"
    amount_unit: str = "paise"
    count: int
    products: list[ProductOut]


class BundleOpportunityOut(BaseModel):
    id: str
    merchant_id: str
    anchor_product_id: str
    companion_product_id: str
    anchor_name: str = ""
    companion_name: str = ""
    potential_aov_uplift: int
    rationale: str
    status: str
