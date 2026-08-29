"""Buyer and Merchant agent behaviour (US-2, US-3, US-5).

The suite runs with no ANTHROPIC_API_KEY, so these exercise the deterministic
paths. That is deliberate: the guarantees below must hold regardless of whether
a model is in the loop, and a test that depends on live model output would be
neither reproducible nor a real check on the guardrails.
"""
import pytest

from app.agents.buyer import BuyerAgent
from app.agents.buyer.parser import parse_intent_deterministic
from app.agents.merchant import MerchantGrowthAgent
from app.enums import OpportunityStatus
from app.models import BundleOpportunity, Product
from app.schemas.agents import ParsedIntent

agent = BuyerAgent()
growth = MerchantGrowthAgent()


# =============================================================== intent parsing
@pytest.mark.parametrize(
    "query,expected_paise",
    [
        ("Buy me headphones under Rs 10,000", 1_000_000),
        ("headphones under 10000", 1_000_000),
        ("headphones, budget 4k", 400_000),
        ("headphones under 1.5 lakh", 15_000_000),
        ("headphones under ₹8,999", 899_900),
    ],
)
def test_budget_is_parsed_into_paise(query, expected_paise):
    """Rupee text in, integer paise out - the only conversion point on input."""
    assert parse_intent_deterministic(query).budget_max == expected_paise


def test_agent_asks_rather_than_assuming_a_budget():
    """US-2: an unstated budget must never be invented."""
    parsed = parse_intent_deterministic("Buy me some good headphones")
    assert parsed.needs_clarification is True
    assert parsed.budget_max is None
    assert parsed.clarification_question


def test_approval_threshold_is_extracted_separately_from_budget():
    parsed = parse_intent_deterministic(
        "Buy me wireless headphones under Rs 10,000, prefer Sony, "
        "don't spend more than 5000 without asking me"
    )
    assert parsed.budget_max == 1_000_000
    assert parsed.require_approval_above == 500_000
    assert "Sony" in parsed.preferred_brands


def test_category_reflects_the_item_being_bought_not_merely_mentioned():
    assert parse_intent_deterministic(
        "Buy me a braided aux cable for my headphones, budget Rs 1000"
    ).category == "accessories"
    assert parse_intent_deterministic(
        "Buy me wireless headphones under Rs 10,000"
    ).category == "electronics"


# ============================================================ candidate ranking
def test_rejections_state_the_specific_shortfall(db):
    """US-3: 'not eligible' is not an explanation; the gap must be quantified."""
    products = db.query(Product).all()
    intent = ParsedIntent(category="electronics", budget_max=1_000_000)
    evaluations = agent.evaluate_candidates(products, intent)

    sennheiser = next(e for e in evaluations if "Sennheiser" in e.name)
    assert sennheiser.eligible is False
    assert "Exceeds budget by Rs 1,999" in sennheiser.rejection_reason


def test_out_of_category_products_are_rejected_with_a_reason(db):
    products = db.query(Product).all()
    evaluations = agent.evaluate_candidates(
        products, ParsedIntent(category="electronics", budget_max=1_000_000)
    )
    cable = next(e for e in evaluations if "AUX Cable" in e.name)
    assert cable.eligible is False
    assert "Category mismatch" in cable.rejection_reason


def test_out_of_stock_products_are_rejected(db):
    product = db.query(Product).filter(Product.id == "prod_sony_whch720n").one()
    product.stock_available = False
    evaluations = agent.evaluate_candidates(
        db.query(Product).all(), ParsedIntent(category="electronics", budget_max=2_000_000)
    )
    sony = next(e for e in evaluations if e.product_id == "prod_sony_whch720n")
    assert sony.eligible is False and "stock" in sony.rejection_reason.lower()


def test_brand_preference_wins_the_ranking(db):
    products = db.query(Product).all()
    rec = agent.recommend(
        products,
        ParsedIntent(category="electronics", budget_max=1_000_000, preferred_brands=["Sony"]),
    )
    assert rec.selected_product_id == "prod_sony_whch720n"
    assert "Sony" in rec.justification


def test_recommended_amount_comes_from_the_catalog_row(db):
    """The chargeable amount is never model-authored - it equals the DB price."""
    products = db.query(Product).all()
    rec = agent.recommend(products, ParsedIntent(category="electronics", budget_max=1_000_000))
    product = db.get(Product, rec.selected_product_id)
    assert rec.amount == product.price


def test_remaining_budget_is_computed_not_narrated(db):
    products = db.query(Product).all()
    rec = agent.recommend(
        products,
        ParsedIntent(category="electronics", budget_max=1_000_000, preferred_brands=["Sony"]),
    )
    assert rec.remaining_budget == 1_000_000 - 899_900


def test_no_eligible_candidate_returns_an_explained_refusal(db):
    products = db.query(Product).all()
    rec = agent.recommend(products, ParsedIntent(category="electronics", budget_max=1_000))
    assert rec.selected_product_id is None
    assert "Exceeds budget" in rec.justification


# ============================================================== bundling (US-5)
def test_bundle_is_offered_for_an_approved_companion(db, merchant):
    anchor = db.get(Product, "prod_sony_whch720n")
    offer = growth.propose_bundle(db, merchant, anchor, remaining_budget=1_000_000)
    assert offer.offered is True
    assert offer.discount_pct <= merchant.max_discount_pct
    assert len(offer.items) == 2


def test_bundle_price_matches_its_stated_discount(db, merchant):
    """Arithmetic the policy engine independently re-derives."""
    anchor = db.get(Product, "prod_sony_whch720n")
    offer = growth.propose_bundle(db, merchant, anchor, remaining_budget=1_000_000)
    expected = offer.list_price - (offer.list_price * offer.discount_pct) // 100
    assert offer.bundle_price == expected


def test_agent_declines_when_no_companion_is_approved(db, merchant):
    """US-5: knowing when NOT to use AI - a forced upsell is worse than none."""
    db.query(BundleOpportunity).update({BundleOpportunity.status: OpportunityStatus.REJECTED})
    db.commit()
    anchor = db.get(Product, "prod_sony_whch720n")
    offer = growth.propose_bundle(db, merchant, anchor, remaining_budget=1_000_000)
    assert offer.offered is False
    assert "no merchant-approved companion" in offer.reasoning.lower()


def test_agent_declines_when_the_bundle_would_break_the_budget(db, merchant):
    """With no discount authority on the anchor, any companion adds real cost.
    Given zero headroom the agent must decline rather than push the upsell."""
    anchor = db.get(Product, "prod_sennheiser_hd450bt")
    anchor.max_discount_pct = 0
    offer = growth.propose_bundle(db, merchant, anchor, remaining_budget=0)
    assert offer.offered is False
    assert "budget" in offer.reasoning.lower()


def test_bundle_discount_respects_the_anchors_own_per_sku_ceiling(db, merchant):
    """A 5%-max SKU must not be discounted 10% just because a companion allows it."""
    anchor = db.get(Product, "prod_sennheiser_hd450bt")   # max_discount_pct = 5
    assert anchor.max_discount_pct == 5
    assert merchant.max_discount_pct == 10
    offer = growth.propose_bundle(db, merchant, anchor, remaining_budget=1_000_000)
    assert offer.offered is True
    assert offer.discount_pct == 5


def test_agent_still_offers_a_bundle_that_costs_less_than_the_anchor_alone(db, merchant):
    """A 10% discount on Rs 9,798 exceeds the Rs 799 case's price, so the bundle
    is genuinely cheaper than the headphones on their own. Declining here would
    be the wrong call, and the affordability check must not mistake it for one."""
    anchor = db.get(Product, "prod_sony_whch720n")
    offer = growth.propose_bundle(db, merchant, anchor, remaining_budget=0)
    assert offer.offered is True
    assert offer.bundle_price <= anchor.price


def test_agent_never_bundles_a_product_with_no_companions(db, merchant):
    cable = db.get(Product, "prod_cable_aux")
    offer = growth.propose_bundle(db, merchant, cable, remaining_budget=1_000_000)
    assert offer.offered is False


def test_proposed_discount_never_exceeds_the_merchant_cap(db, merchant):
    merchant.max_discount_pct = 3
    anchor = db.get(Product, "prod_sony_whch720n")
    offer = growth.propose_bundle(db, merchant, anchor, remaining_budget=1_000_000)
    assert offer.discount_pct <= 3
