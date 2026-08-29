"""Money representation (PRD 5.7 Q1).

The decision was paise-everywhere as integers. These tests guard the two ways
that decision could quietly break: a float creeping into a monetary path, or a
100x error at a conversion boundary.
"""
import pytest
from sqlalchemy import select

from app.models import Product, PurchaseIntent, Transaction
from app.schemas.agents import ShoppingRequest
from app.services.money import format_inr, rupees, to_paise
from app.services.orchestrator import run_shopping_flow


@pytest.mark.parametrize(
    "paise,expected",
    [
        (0, "Rs 0"),
        (100, "Rs 1"),
        (29_900, "Rs 299"),
        (899_900, "Rs 8,999"),
        (1_000_000, "Rs 10,000"),
        (15_000_000, "Rs 1,50,000"),      # Indian grouping, not 150,000
        (1_00_00_000, "Rs 1,00,000"),
        (881_820, "Rs 8,818.20"),         # paise remainder is preserved
    ],
)
def test_inr_formatting_uses_indian_grouping(paise, expected):
    assert format_inr(paise) == expected


@pytest.mark.parametrize(
    "rupee_input,expected_paise",
    [(1, 100), (299, 29_900), (8_999, 899_900), (0.5, 50), (1.005, 100)],
)
def test_rupee_to_paise_conversion(rupee_input, expected_paise):
    assert to_paise(rupee_input) == expected_paise
    assert isinstance(to_paise(rupee_input), int)


def test_rupees_helper_truncates_rather_than_rounding_up():
    """Display-only truncation must never overstate what was charged."""
    assert rupees(29_999) == 299


def test_every_catalog_price_is_a_positive_integer(db):
    for product in db.scalars(select(Product)):
        assert isinstance(product.price, int)
        assert not isinstance(product.price, bool)
        assert product.price > 0


def test_charged_amount_equals_the_catalog_price_exactly(db, buyer):
    """The anti-hallucination guarantee, end to end."""
    result = run_shopping_flow(
        db,
        ShoppingRequest(query="Buy me a braided aux cable for my headphones, budget Rs 1000"),
        buyer,
    )
    product = db.get(Product, "prod_cable_aux")
    intent = db.get(PurchaseIntent, result.intent.intent_id)
    txn = db.scalar(select(Transaction).where(Transaction.purchase_intent_id == intent.id))

    assert product.price == 29_900
    assert intent.amount == product.price
    assert txn.amount == product.price
    assert result.recommendation.amount == product.price
    # every hop stayed an int - no float ever touched the amount
    assert all(isinstance(v, int) for v in (intent.amount, txn.amount))


def test_no_monetary_value_is_stored_as_a_float(db, buyer):
    run_shopping_flow(
        db,
        ShoppingRequest(query="Buy me a braided aux cable for my headphones, budget Rs 1000"),
        buyer,
    )
    for txn in db.scalars(select(Transaction)):
        assert isinstance(txn.amount, int)
    for intent in db.scalars(select(PurchaseIntent)):
        assert isinstance(intent.amount, int)


def test_bundle_discount_arithmetic_stays_integral(db, merchant):
    """Floor division keeps the result an int and never rounds in the buyer's favour by accident."""
    from app.agents.merchant import MerchantGrowthAgent

    anchor = db.get(Product, "prod_sony_whch720n")
    offer = MerchantGrowthAgent().propose_bundle(db, merchant, anchor, remaining_budget=1_000_000)
    assert isinstance(offer.bundle_price, int)
    assert isinstance(offer.list_price, int)
    assert offer.bundle_price <= offer.list_price
