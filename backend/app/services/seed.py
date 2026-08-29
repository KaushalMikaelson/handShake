"""Demo seed data.

Scope per PRD section 4: ONE merchant, 3 SKUs in the primary category
(wireless headphones), plus 2 SKUs in a second category (accessories) to
demonstrate cross-category bundling - the explicitly-allowed [P2] stretch.
"""
import uuid

from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    BundleOpportunity,
    Buyer,
    Merchant,
    OpportunityStatus,
    Product,
)
from app.enums import AutonomyLevel, UserRole

MERCHANT_ID = settings.demo_merchant_id
BUYER_ID = settings.demo_buyer_id

# --- primary category: wireless headphones (3 SKUs, US-1) ---
PRODUCTS = [
    dict(
        id="prod_sony_whch720n",
        name="Sony WH-CH720N Wireless Noise Cancelling Headphones",
        brand="Sony",
        price=899_900,          # Rs 8,999
        category="electronics",
        attributes=["wireless", "noise-cancelling", "over-ear", "35h-battery", "bluetooth-5.2"],
        bundle_eligible=True,
        max_discount_pct=10,
        companion_product_ids=["prod_case_hardshell", "prod_cable_aux"],
    ),
    dict(
        id="prod_boat_rockerz_551",
        name="boAt Rockerz 551ANC Wireless Headphones",
        brand="boAt",
        price=349_900,          # Rs 3,499
        category="electronics",
        attributes=["wireless", "noise-cancelling", "over-ear", "60h-battery", "bluetooth-5.3"],
        bundle_eligible=True,
        max_discount_pct=8,
        companion_product_ids=["prod_case_hardshell"],
    ),
    dict(
        id="prod_sennheiser_hd450bt",
        name="Sennheiser HD 450BT Wireless Headphones",
        brand="Sennheiser",
        price=1_199_900,        # Rs 11,999
        category="electronics",
        attributes=["wireless", "noise-cancelling", "over-ear", "30h-battery", "aptx-codec"],
        bundle_eligible=True,
        max_discount_pct=5,
        companion_product_ids=["prod_case_hardshell", "prod_cable_aux"],
    ),
    # --- second category: accessories ([P2] cross-category bundling) ---
    dict(
        id="prod_case_hardshell",
        name="Universal Hardshell Headphone Carry Case",
        brand="AudioHub",
        price=79_900,           # Rs 799
        category="accessories",
        attributes=["hardshell", "water-resistant", "universal-fit"],
        bundle_eligible=True,
        max_discount_pct=15,
        companion_product_ids=[],
    ),
    dict(
        id="prod_cable_aux",
        name="Braided 3.5mm AUX Cable (1.5m)",
        brand="AudioHub",
        price=29_900,           # Rs 299
        category="accessories",
        attributes=["braided", "3.5mm", "1.5m", "gold-plated"],
        bundle_eligible=True,
        max_discount_pct=20,
        companion_product_ids=[],
    ),
]


def seed_if_empty(db: Session) -> bool:
    """Idempotent seed. Returns True if data was written."""
    if db.query(Merchant).count() > 0:
        return False

    merchant = Merchant(
        id=MERCHANT_ID,
        name="AudioHub India",
        description="Audio gear merchant with an AI growth agent for bundling and upsell.",
        max_discount_pct=10,
        max_campaign_budget=2_500_000,          # Rs 25,000
        auto_approve_bundle_discount_below_pct=5,
        verified_catalog=True,
        successful_transactions=42,
        failed_transactions=1,
    )
    db.add(merchant)

    for spec in PRODUCTS:
        db.add(Product(merchant_id=MERCHANT_ID, currency="INR", stock_available=True, **spec))

    # Flush before inserting opportunities. BundleOpportunity references
    # merchants and products by raw FK columns with no relationship(), so
    # SQLAlchemy cannot infer the insert order on its own - and Postgres
    # enforces the constraint even though SQLite silently would not.
    db.flush()

    db.add(
        Buyer(
            id=BUYER_ID,
            name="Aditi",
            daily_budget=1_500_000,             # Rs 15,000
            monthly_budget=5_000_000,           # Rs 50,000
            max_transaction=1_000_000,          # Rs 10,000
            allowed_categories=["electronics", "accessories"],
            blocked_categories=["financial_services"],
            require_approval_above=500_000,     # Rs 5,000
            allow_automatic_purchase_below=200_000,  # Rs 2,000
            autonomy_level=AutonomyLevel.BOUNDED_AUTO,
        )
    )

    _seed_opportunities(db)
    db.flush()
    _seed_users(db)
    db.commit()
    return True


# Demo credentials. Printed on the login screen so a judge can sign in in
# seconds; the password still satisfies the real password policy, so the
# hashing path being exercised is the production one.
DEMO_PASSWORD = "Demo@1234"

DEMO_USERS = [
    dict(
        email="aditi@handshake.demo",
        name="Aditi Rao",
        role=UserRole.BUYER,
        buyer_id=BUYER_ID,
        merchant_id=None,
    ),
    dict(
        email="merchant@audiohub.demo",
        name="AudioHub Growth Team",
        role=UserRole.MERCHANT,
        buyer_id=None,
        merchant_id=MERCHANT_ID,
    ),
    dict(
        email="admin@handshake.demo",
        name="Platform Admin",
        role=UserRole.ADMIN,
        buyer_id=BUYER_ID,
        merchant_id=MERCHANT_ID,
    ),
]


def _seed_users(db: Session) -> None:
    """Create the three demo logins.

    Imported lazily so the seed module stays importable without bcrypt in
    contexts that only need catalog data.
    """
    from app.services.auth import create_user

    for spec in DEMO_USERS:
        create_user(db, password=DEMO_PASSWORD, **spec)


def create_buyer_profile(db: Session, *, name: str) -> Buyer:
    """A policy row for a newly registered buyer.

    Defaults are deliberately conservative - a brand-new account gets a small
    daily budget and must approve almost everything. Widening those limits is
    an explicit, human action on the Buyer dashboard.
    """
    buyer = Buyer(
        id=f"buyer_{uuid.uuid4().hex[:10]}",
        name=name,
        daily_budget=500_000,                    # Rs 5,000
        monthly_budget=2_000_000,                # Rs 20,000
        max_transaction=300_000,                 # Rs 3,000
        allowed_categories=["electronics", "accessories"],
        blocked_categories=["financial_services"],
        require_approval_above=100_000,          # Rs 1,000
        allow_automatic_purchase_below=50_000,   # Rs 500
        autonomy_level=AutonomyLevel.PREPARE,    # ask every time, until widened
    )
    db.add(buyer)
    db.flush()
    return buyer


def _seed_opportunities(db: Session) -> None:
    """US-5b - derived from catalog companion relationships, not an ML model."""
    by_id = {p["id"]: p for p in PRODUCTS}
    for anchor in PRODUCTS:
        for companion_id in anchor["companion_product_ids"]:
            companion = by_id[companion_id]
            db.add(
                BundleOpportunity(
                    id=f"opp_{uuid.uuid4().hex[:10]}",
                    merchant_id=MERCHANT_ID,
                    anchor_product_id=anchor["id"],
                    companion_product_id=companion_id,
                    potential_aov_uplift=companion["price"],
                    rationale=(
                        f"Buyers of {anchor['brand']} {anchor['category']} frequently need "
                        f"{companion['name'].lower()}; attaching it lifts order value by "
                        f"{companion['price'] // 100} rupees."
                    ),
                    # Pre-approved so the happy path works out of the box; the
                    # merchant can reject them from the dashboard (US-5b).
                    status=OpportunityStatus.APPROVED,
                )
            )
