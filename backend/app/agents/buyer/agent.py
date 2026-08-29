"""Buyer Agent (US-2, US-3, US-4).

Division of labour, which is the whole point of the design:

  * The LLM ranks and explains. It decides which product best fits a stated
    need and writes the human-readable justification.
  * Plain Python decides eligibility and every number. Budget comparisons are
    integer arithmetic on catalog-sourced paise. The final chargeable amount is
    re-read from the Product row by product_id, so even a model that returns a
    confidently wrong price cannot change what gets charged.

If the LLM picks a product that fails a hard eligibility check, the agent
overrides it and falls back to the best eligible candidate. Model output is a
suggestion; the rules are the authority.
"""
from __future__ import annotations

from app.agents.buyer.parser import parse_intent
from app.agents.llm import get_llm_client
from app.models import Product
from app.schemas.agents import CandidateEvaluation, ParsedIntent, Recommendation
from app.services.money import format_inr

RANKING_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "selected_product_id": {
            "type": "string",
            "description": "product_id of the single best ELIGIBLE product for this shopper.",
        },
        "justification": {
            "type": "string",
            "description": (
                "1-2 plain sentences for the shopper explaining why this product was "
                "chosen. Reference the evidence (brand match, features, price). Do not "
                "describe your reasoning process - state the business reason."
            ),
        },
        "candidate_notes": {
            "type": "array",
            "description": "One short note per candidate explaining its fit.",
            "items": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string"},
                    "note": {"type": "string"},
                },
                "required": ["product_id", "note"],
            },
        },
    },
    "required": ["selected_product_id", "justification"],
}

SYSTEM_PROMPT = (
    "You are a buying agent that ranks products for a shopper. You will be given "
    "the shopper's requirements and a list of candidate products, each already "
    "marked ELIGIBLE or REJECTED by a deterministic policy layer. "
    "You may ONLY select from products marked ELIGIBLE. "
    "You do not compute prices, you do not authorise payment, and you must never "
    "state a price other than the one given to you. "
    "Explain decisions in business terms - inputs, evidence, and the rule applied - "
    "never your internal reasoning process."
)


class BuyerAgent:
    agent_id = "buyer_agent"

    def parse(self, query: str) -> tuple[ParsedIntent, str]:
        return parse_intent(query)

    # ------------------------------------------------------------------
    # Eligibility: deterministic, never delegated to the model (US-3)
    # ------------------------------------------------------------------
    def evaluate_candidates(
        self, products: list[Product], intent: ParsedIntent
    ) -> list[CandidateEvaluation]:
        evaluations: list[CandidateEvaluation] = []
        preferred = {b.lower() for b in intent.preferred_brands}

        for product in products:
            reasons: list[str] = []
            rejection: str | None = None

            if intent.category and product.category.lower() != intent.category.lower():
                rejection = (
                    f"Category mismatch: this is '{product.category}', "
                    f"you asked for '{intent.category}'."
                )
            elif not product.stock_available:
                rejection = "Out of stock."
            elif intent.budget_max is not None and product.price > intent.budget_max:
                over = product.price - intent.budget_max
                rejection = (
                    f"Exceeds budget by {format_inr(over)} "
                    f"({format_inr(product.price)} vs {format_inr(intent.budget_max)})."
                )

            if rejection is None:
                reasons.append(f"Matches requested category '{product.category}'")
                if preferred and product.brand.lower() in preferred:
                    reasons.append(f"Matches preferred brand {product.brand}")
                if intent.budget_max is not None:
                    reasons.append(f"Within budget ({format_inr(intent.budget_max)})")
                reasons.append("In stock")

            # Ranking score: brand preference dominates, then feature richness,
            # then value for money. Only ever used to order eligible candidates.
            score = 0.0
            if rejection is None:
                if preferred and product.brand.lower() in preferred:
                    score += 100.0
                score += len(product.attributes or []) * 2.0
                if intent.budget_max:
                    headroom = (intent.budget_max - product.price) / max(intent.budget_max, 1)
                    score += headroom * 10.0

            evaluations.append(
                CandidateEvaluation(
                    product_id=product.id,
                    name=product.name,
                    price=product.price,
                    eligible=rejection is None,
                    reasons=reasons,
                    rejection_reason=rejection,
                    justification="",
                    score=round(score, 2),
                )
            )
        return evaluations

    # ------------------------------------------------------------------
    # Ranking + explanation: LLM-preferred, deterministic fallback
    # ------------------------------------------------------------------
    def recommend(
        self, products: list[Product], intent: ParsedIntent
    ) -> Recommendation:
        evaluations = self.evaluate_candidates(products, intent)
        eligible = [e for e in evaluations if e.eligible]
        by_id = {p.id: p for p in products}

        if not eligible:
            return Recommendation(
                selected_product_id=None,
                justification=(
                    "No product in this merchant's catalog satisfies your constraints. "
                    + " ".join(
                        f"{e.name}: {e.rejection_reason}"
                        for e in evaluations
                        if e.rejection_reason
                    )
                ),
                candidates=evaluations,
                decision_factors=["No eligible candidate"],
                llm_mode="deterministic",
            )

        ranked = sorted(eligible, key=lambda e: e.score, reverse=True)
        chosen = ranked[0]
        mode = "deterministic"
        justification = self._deterministic_justification(by_id[chosen.product_id], intent)

        llm = self._rank_with_llm(evaluations, intent)
        if llm is not None:
            picked_id, llm_justification, notes = llm
            # Guardrail: the model may only pick from the eligible set. If it
            # names anything else we keep the deterministic winner.
            if picked_id in {e.product_id for e in eligible}:
                chosen = next(e for e in eligible if e.product_id == picked_id)
                justification = llm_justification
                mode = "anthropic"
                for e in evaluations:
                    if e.product_id in notes:
                        e.justification = notes[e.product_id]

        for e in evaluations:
            if not e.justification:
                e.justification = (
                    ", ".join(e.reasons) if e.eligible else (e.rejection_reason or "")
                )

        product = by_id[chosen.product_id]
        remaining = (
            intent.budget_max - product.price if intent.budget_max is not None else None
        )
        return Recommendation(
            selected_product_id=product.id,
            selected_name=product.name,
            # Authoritative amount: read straight off the catalog row.
            amount=product.price,
            remaining_budget=remaining,
            justification=justification,
            candidates=evaluations,
            decision_factors=chosen.reasons,
            llm_mode=mode,
        )

    def _deterministic_justification(self, product: Product, intent: ParsedIntent) -> str:
        bits = [f"{product.name} at {format_inr(product.price)}"]
        if intent.preferred_brands and product.brand.lower() in {
            b.lower() for b in intent.preferred_brands
        }:
            bits.append(f"matches your preferred brand {product.brand}")
        if intent.budget_max is not None:
            bits.append(
                f"leaves {format_inr(intent.budget_max - product.price)} of your "
                f"{format_inr(intent.budget_max)} budget"
            )
        features = ", ".join((product.attributes or [])[:3])
        if features:
            bits.append(f"and offers {features}")
        return "Selected " + " ".join(bits) + "."

    def _rank_with_llm(
        self, evaluations: list[CandidateEvaluation], intent: ParsedIntent
    ) -> tuple[str, str, dict[str, str]] | None:
        client = get_llm_client()
        if not client.live:
            return None

        lines = []
        for e in evaluations:
            status = "ELIGIBLE" if e.eligible else f"REJECTED ({e.rejection_reason})"
            lines.append(
                f"- product_id={e.product_id} | {e.name} | {format_inr(e.price)} | {status}"
            )
        prompt = (
            f"Shopper requirements:\n"
            f"  category: {intent.category}\n"
            f"  budget_max: {format_inr(intent.budget_max) if intent.budget_max else 'not set'}\n"
            f"  preferred_brands: {', '.join(intent.preferred_brands) or 'none'}\n"
            f"  use_case: {intent.use_case}\n\n"
            f"Candidates:\n" + "\n".join(lines) + "\n\n"
            "Select the single best ELIGIBLE product and justify it for the shopper."
        )
        result = client.structured_call(
            system=SYSTEM_PROMPT,
            prompt=prompt,
            tool_name="record_product_selection",
            tool_description="Record the selected product and the justification for the shopper.",
            input_schema=RANKING_TOOL_SCHEMA,
        )
        if result.mode != "anthropic" or not result.data:
            return None
        picked = str(result.data.get("selected_product_id", ""))
        justification = str(result.data.get("justification", "")).strip()
        notes = {
            str(n.get("product_id")): str(n.get("note", ""))
            for n in result.data.get("candidate_notes", [])
            if isinstance(n, dict)
        }
        if not picked or not justification:
            return None
        return picked, justification, notes
