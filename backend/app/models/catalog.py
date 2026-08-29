"""Merchant + product catalog models.

All money is stored as integer paise. There is exactly one currency conversion
boundary in the system (the UI formatter); nothing server-side ever handles
rupees as a float. See docs/architecture.md "Money representation".
"""
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base
from app.enums import OpportunityStatus


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Merchant(Base):
    __tablename__ = "merchants"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(500), default="")

    # --- merchant-side policy config (PRD 3.4) ---
    max_discount_pct: Mapped[int] = mapped_column(Integer, default=10)
    max_campaign_budget: Mapped[int] = mapped_column(Integer, default=2_500_000)
    auto_approve_bundle_discount_below_pct: Mapped[int] = mapped_column(Integer, default=5)

    # --- trust engine inputs (US-11, advisory only) ---
    verified_catalog: Mapped[bool] = mapped_column(Boolean, default=True)
    successful_transactions: Mapped[int] = mapped_column(Integer, default=0)
    failed_transactions: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    products: Mapped[list["Product"]] = relationship(back_populates="merchant")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    brand: Mapped[str] = mapped_column(String(100), default="")

    price: Mapped[int] = mapped_column(Integer, nullable=False)  # paise
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    stock_available: Mapped[bool] = mapped_column(Boolean, default=True)
    attributes: Mapped[list] = mapped_column(JSON, default=list)
    bundle_eligible: Mapped[bool] = mapped_column(Boolean, default=False)
    max_discount_pct: Mapped[int] = mapped_column(Integer, default=0)
    # companion SKUs the merchant agent may bundle with this anchor product
    companion_product_ids: Mapped[list] = mapped_column(JSON, default=list)

    merchant: Mapped[Merchant] = relationship(back_populates="products")


class BundleOpportunity(Base):
    """US-5b - AI-identified growth opportunities, human-gated before use.

    Derived from catalog `companion_product_ids` relationships, not a live ML
    recommender (explicitly out of scope, PRD section 4).
    """

    __tablename__ = "bundle_opportunities"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    merchant_id: Mapped[str] = mapped_column(ForeignKey("merchants.id"), nullable=False)
    anchor_product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False)
    companion_product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False)
    potential_aov_uplift: Mapped[int] = mapped_column(Integer, default=0)  # paise
    rationale: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(32), default=OpportunityStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
