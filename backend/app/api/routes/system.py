"""System/meta endpoints - what mode everything is running in."""
from fastapi import APIRouter

from app.agents.llm import get_llm_client
from app.config import settings
from app.payments.razorpay_service import get_payment_client
from app.policies.permission import BUYER_AGENT_PERMISSIONS, MERCHANT_AGENT_PERMISSIONS

router = APIRouter(tags=["system"])


@router.get("/health")
def health():
    return {"status": "ok", "app": settings.app_name}


@router.get("/system/status")
def system_status():
    """Surfaces which integrations are live vs simulated, so a demo never lies."""
    payments = get_payment_client()
    llm = get_llm_client()
    return {
        "environment": settings.environment,
        "payments": {
            "mode": payments.mode,
            "live": payments.live,
            "note": (
                "Razorpay test-mode credentials configured."
                if payments.live
                else "No Razorpay credentials: using the in-process simulator. "
                     "Set RAZORPAY_KEY_ID/SECRET to switch to test mode."
            ),
            "calls_made": payments.call_count,
        },
        "llm": {
            "mode": "anthropic" if llm.live else "deterministic",
            "live": llm.live,
            "model": settings.anthropic_model if llm.live else None,
            "note": (
                "Anthropic structured output active."
                if llm.live
                else "No ANTHROPIC_API_KEY: agents use their deterministic rule-based "
                     "path. Every guardrail behaves identically either way."
            ),
        },
        "permissions": {
            "buyer_agent": {
                "allowed": BUYER_AGENT_PERMISSIONS.allowed_names,
                "denied": BUYER_AGENT_PERMISSIONS.denied_names,
            },
            "merchant_agent": {
                "allowed": MERCHANT_AGENT_PERMISSIONS.allowed_names,
                "denied": MERCHANT_AGENT_PERMISSIONS.denied_names,
            },
        },
        "security_principles": [
            "The LLM never directly controls money.",
            "The LLM cannot modify policies.",
            "The LLM cannot grant itself permissions.",
            "Every financial operation is validated deterministically.",
            "Every payment operation is auditable.",
            "Unknown payment states must never trigger blind retries.",
            "Hard financial limits override AI recommendations - always.",
        ],
    }
