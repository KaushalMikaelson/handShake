"""Autonomy routing (US-6b) - decides who authorises a purchase that passed policy.

This runs only after every hard rule has passed. It never turns a BLOCKED
verdict into an allowed one; it only chooses between "the agent may proceed on
its own" and "a human must press Approve".
"""
from app.enums import AutonomyLevel
from app.policies.models import BuyerPolicy, PolicyOutcome, ProposedPurchase
from app.services.money import format_inr


def route_authority(
    purchase: ProposedPurchase, policy: BuyerPolicy
) -> tuple[PolicyOutcome, str]:
    """Return the authorisation route and a human-readable reason."""
    level = policy.autonomy_level

    if level == AutonomyLevel.RECOMMEND:
        return (
            PolicyOutcome.RECOMMEND_ONLY,
            "Autonomy Level 1 (Recommend): the agent may suggest this product but "
            "cannot create a purchase intent.",
        )

    if level == AutonomyLevel.PREPARE:
        return (
            PolicyOutcome.REQUIRES_APPROVAL,
            "Autonomy Level 2 (Prepare): every purchase requires human approval "
            "regardless of amount.",
        )

    # --- Level 3: bounded auto-purchase ---
    if purchase.amount >= policy.require_approval_above:
        return (
            PolicyOutcome.REQUIRES_APPROVAL,
            f"{format_inr(purchase.amount)} is at or above the approval threshold of "
            f"{format_inr(policy.require_approval_above)}, so a human must approve it.",
        )

    if purchase.amount < policy.allow_automatic_purchase_below:
        return (
            PolicyOutcome.AUTO_APPROVE,
            f"{format_inr(purchase.amount)} is below the automatic-purchase threshold "
            f"of {format_inr(policy.allow_automatic_purchase_below)} and passed every "
            f"policy check, so the agent may proceed autonomously.",
        )

    # Between allow_automatic_purchase_below and require_approval_above the
    # buyer has expressed no automatic authority, so we default to asking.
    return (
        PolicyOutcome.REQUIRES_APPROVAL,
        f"{format_inr(purchase.amount)} sits between the auto-purchase ceiling "
        f"({format_inr(policy.allow_automatic_purchase_below)}) and the approval "
        f"threshold ({format_inr(policy.require_approval_above)}); the safe default "
        f"in that band is to ask.",
    )
