"""Trust Engine (US-11) - advisory ranking signal, nothing more.

Deliberately a small set of rule-derived checks over data we already have, not
a learned reputation model (explicitly out of scope, PRD section 4).

The load-bearing property is what this module CANNOT do: it returns a score and
some signals, and no caller passes that score into the policy engine. A 100/100
merchant offering a product above the buyer's limit is still BLOCKED -
`tests/test_trust_engine.py` asserts exactly that case.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.models import Merchant, Product


@dataclass
class TrustSignal:
    name: str
    passed: bool
    weight: int
    detail: str


@dataclass
class TrustReport:
    merchant_id: str
    score: int
    band: str
    signals: list[TrustSignal] = field(default_factory=list)
    advisory_note: str = (
        "Trust is an advisory ranking signal only. It cannot raise a spending limit, "
        "relax a policy rule, or authorise a blocked purchase."
    )

    def to_dict(self) -> dict:
        return {
            "merchant_id": self.merchant_id,
            "score": self.score,
            "band": self.band,
            "signals": [
                {
                    "name": s.name,
                    "passed": s.passed,
                    "weight": s.weight,
                    "detail": s.detail,
                }
                for s in self.signals
            ],
            "advisory_note": self.advisory_note,
        }


class TrustEngine:
    def evaluate(self, merchant: Merchant, products: list[Product]) -> TrustReport:
        signals: list[TrustSignal] = []

        signals.append(
            TrustSignal(
                name="catalog_verified",
                passed=bool(merchant.verified_catalog),
                weight=20,
                detail="Merchant catalog has been verified."
                if merchant.verified_catalog
                else "Merchant catalog is unverified.",
            )
        )

        complete = [
            p for p in products if p.name and p.price > 0 and p.category and p.attributes
        ]
        completeness_ok = bool(products) and len(complete) == len(products)
        signals.append(
            TrustSignal(
                name="catalog_completeness",
                passed=completeness_ok,
                weight=20,
                detail=(
                    f"{len(complete)}/{len(products)} SKUs carry complete "
                    f"name, price, category and attributes."
                ),
            )
        )

        priced_sanely = all(p.price > 0 for p in products) if products else False
        signals.append(
            TrustSignal(
                name="pricing_consistent",
                passed=priced_sanely,
                weight=20,
                detail="All SKUs carry a positive integer price in paise."
                if priced_sanely
                else "One or more SKUs have a non-positive price.",
            )
        )

        discounts_bounded = all(
            0 <= p.max_discount_pct <= merchant.max_discount_pct + 10 for p in products
        ) if products else False
        signals.append(
            TrustSignal(
                name="discount_policy_declared",
                passed=discounts_bounded,
                weight=15,
                detail=(
                    f"Per-SKU discount ceilings are declared and bounded "
                    f"(merchant max {merchant.max_discount_pct}%)."
                ),
            )
        )

        total = merchant.successful_transactions + merchant.failed_transactions
        success_rate = merchant.successful_transactions / total if total else 0.0
        fulfilment_ok = total >= 5 and success_rate >= 0.9
        signals.append(
            TrustSignal(
                name="fulfilment_history",
                passed=fulfilment_ok,
                weight=25,
                detail=(
                    f"{merchant.successful_transactions} settled / {total} attempted "
                    f"({success_rate:.0%} success)."
                ),
            )
        )

        score = sum(s.weight for s in signals if s.passed)
        return TrustReport(
            merchant_id=merchant.id,
            score=score,
            band=self._band(score),
            signals=signals,
        )

    @staticmethod
    def _band(score: int) -> str:
        if score >= 85:
            return "HIGH"
        if score >= 60:
            return "MODERATE"
        return "LOW"


_engine = TrustEngine()


def evaluate_trust(merchant: Merchant, products: list[Product]) -> TrustReport:
    return _engine.evaluate(merchant, products)
