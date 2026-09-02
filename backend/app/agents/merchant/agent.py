"""Merchant Growth Agent (US-5, US-5b).

Proposes a bundle for a given PurchaseIntent, or explicitly declines. The
decline path is a feature, not a gap: forcing an upsell onto every transaction
is exactly the failure mode "knowing when not to use AI" is meant to catch, so
`no_bundle_offered` with a stated reason is a first-class outcome.

Two things bound this agent:
  * It may only bundle companions the merchant has APPROVED (US-5b), so a human
    has signed off on the pairing before any buyer ever sees it.
  * Its proposed discount is only a proposal. The Policy Engine checks it
    against max_discount_pct, and separately re-derives the arithmetic, so a
    model that proposes "5% off" while quoting a 40%-off number is caught.
"""
from __future__ import annotations

from app.agents.llm import get_llm_client
from app.models import BundleOpportunity, OpportunityStatus, Merchant, Product
from app.schemas.agents import BundleItem, BundleOffer
from app.services.money import format_inr

BUNDLE_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "offer_bundle": {
            "type": "boolean",
            "description": (
                "True only if the companion genuinely complements the purchase AND "
                "fits the shopper's remaining budget. False if no sensible bundle exists."
            ),
        },
        "companion_product_id": {
            "type": "string",
            "description": "product_id of the companion to bundle. Omit if offer_bundle is false.",
        },
        "discount_pct": {
            "type": "integer",
            "description": (
                "Whole-percent discount to propose on the combined list price. "
                "Must not exceed the stated max_discount_pct."
            ),
        },
        "reasoning": {
            "type": "string",
            "description": (
                "One sentence for the shopper explaining the bundle - or, if declining, "
                "why no bundle is appropriate here."
            ),
        },
    },
    "required": ["offer_bundle", "reasoning"],
}

SYSTEM_PROMPT = (
    "You are a merchant's growth agent. Given a shopper's chosen product and a list of "
    "merchant-approved companion products, propose at most one bundle that raises order "
    "value while genuinely serving the shopper. "
    "Decline (offer_bundle=false) when no companion is a real fit or the bundle would "
    "not fit the shopper's remaining budget - a forced upsell is worse than none. "
    "You propose discounts; you do not authorise them, and you never modify catalog "
    "pricing. Never exceed the max_discount_pct you are given."
)


class MerchantGrowthAgent:
    agent_id = "merchant_agent"

    def approved_companions(
        self, db, merchant_id: str, anchor_product_id: str
    ) -> list[Product]:
        """Companions the merchant has explicitly approved for this anchor (US-5b)."""
        opportunities = (
            db.query(BundleOpportunity)
            .filter(
                BundleOpportunity.merchant_id == merchant_id,
                BundleOpportunity.anchor_product_id == anchor_product_id,
                BundleOpportunity.status == OpportunityStatus.APPROVED,
            )
            .all()
        )
        companion_ids = [o.companion_product_id for o in opportunities]
        if not companion_ids:
            return []
        return (
            db.query(Product)
            .filter(
                Product.id.in_(companion_ids),
                Product.bundle_eligible.is_(True),
                Product.stock_available.is_(True),
            )
            .all()
        )

    def propose_bundle(
        self,
        db,
        merchant: Merchant,
        anchor: Product,
        remaining_budget: int | None,
    ) -> BundleOffer:
        companions = self.approved_companions(db, merchant.id, anchor.id)

        if not companions:
            return BundleOffer(
                offered=False,
                reasoning=(
                    f"No merchant-approved companion product exists for "
                    f"{anchor.name}, so no bundle is offered."
                ),
                llm_mode="deterministic",
            )

        affordable = self._affordable(companions, anchor, merchant, remaining_budget)
        if not affordable:
            return BundleOffer(
                offered=False,
                reasoning=(
                    "A companion product is available, but bundling it would push the "
                    "order past the shopper's remaining budget, so no bundle is offered."
                ),
                llm_mode="deterministic",
            )

        # deterministic default: best uplift the merchant is allowed to discount
        companion = max(affordable, key=lambda p: p.price)
        discount_pct = self._discount_ceiling(merchant, anchor, companion)
        mode = "deterministic"
        reasoning = (
            f"{companion.name} pairs directly with {anchor.name}; bundling them saves "
            f"{discount_pct}% versus buying separately."
        )

        llm = self._propose_with_llm(merchant, anchor, affordable, remaining_budget)
        if llm is not None:
            offer_bundle, companion_id, llm_discount, llm_reason, llm_mode = llm
            if not offer_bundle:
                return BundleOffer(
                    offered=False,
                    reasoning=llm_reason
                    or "The growth agent judged that no bundle suits this purchase.",
                    llm_mode=llm_mode,
                )
            match = next((c for c in affordable if c.id == companion_id), None)
            if match is not None:
                companion = match
                # The model's number is clamped here and re-checked by the
                # Policy Engine; two independent bounds on the same value.
                discount_pct = max(
                    0, min(int(llm_discount), self._discount_ceiling(merchant, anchor, companion))
                )
                reasoning = llm_reason or reasoning
                mode = llm_mode


        list_price = anchor.price + companion.price
        # Integer arithmetic, floor-rounded - the same formula the policy engine
        # re-derives independently in check_bundle_price_integrity.
        bundle_price = list_price - (list_price * discount_pct) // 100

        return BundleOffer(
            offered=True,
            items=[
                BundleItem(product_id=anchor.id, name=anchor.name, price=anchor.price),
                BundleItem(
                    product_id=companion.id, name=companion.name, price=companion.price
                ),
            ],
            bundle_price=bundle_price,
            list_price=list_price,
            discount_pct=discount_pct,
            reasoning=reasoning,
            llm_mode=mode,
        )

    @staticmethod
    def _discount_ceiling(merchant: Merchant, anchor: Product, companion: Product) -> int:
        """The lowest ceiling that applies to this bundle.

        A bundle is bound by the merchant's cap AND by the per-SKU ceiling of
        every item in it - discounting a bundle by more than its most-protected
        SKU allows would launder a margin breach through the bundling flow.
        """
        return min(merchant.max_discount_pct, anchor.max_discount_pct, companion.max_discount_pct)

    def _affordable(
        self,
        companions: list[Product],
        anchor: Product,
        merchant: Merchant,
        remaining_budget: int | None,
    ) -> list[Product]:
        if remaining_budget is None:
            return list(companions)
        out = []
        for c in companions:
            discount_pct = self._discount_ceiling(merchant, anchor, c)
            list_price = anchor.price + c.price
            bundle_price = list_price - (list_price * discount_pct) // 100
            # remaining_budget is what's left after the anchor, so the bundle
            # must fit within anchor price + that headroom
            if bundle_price <= anchor.price + remaining_budget:
                out.append(c)
        return out

    def _propose_with_llm(
        self,
        merchant: Merchant,
        anchor: Product,
        companions: list[Product],
        remaining_budget: int | None,
    ) -> tuple[bool, str, int, str, str] | None:
        client = get_llm_client()
        if not client.live:
            return None

        lines = [
            f"- product_id={c.id} | {c.name} | {format_inr(c.price)} | "
            f"category={c.category} | max_discount_pct="
            f"{self._discount_ceiling(merchant, anchor, c)}"
            for c in companions
        ]
        prompt = (
            f"Shopper is buying: {anchor.name} ({anchor.category}) at "
            f"{format_inr(anchor.price)}.\n"
            f"Shopper's remaining budget after this purchase: "
            f"{format_inr(remaining_budget) if remaining_budget is not None else 'unknown'}.\n"
            f"Your maximum authorised discount for this anchor: "
            f"{min(merchant.max_discount_pct, anchor.max_discount_pct)}%.\n\n"
            f"Merchant-approved companion products:\n" + "\n".join(lines) + "\n\n"
            "Propose at most one bundle, or decline."
        )
        result = client.structured_call(
            system=SYSTEM_PROMPT,
            prompt=prompt,
            tool_name="record_bundle_decision",
            tool_description="Record the bundle proposal, or the decision not to offer one.",
            input_schema=BUNDLE_TOOL_SCHEMA,
        )
        if result.mode == "deterministic" or not result.data:
            return None
        data = result.data
        return (
            bool(data.get("offer_bundle")),
            str(data.get("companion_product_id", "")),
            int(data.get("discount_pct", 0) or 0),
            str(data.get("reasoning", "")).strip(),
            result.mode,
        )

