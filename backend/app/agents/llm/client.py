"""Anthropic client wrapper - structured output only.

Two hard rules encoded here:

1. Structured output only. The model is called with a tool schema and we read
   `tool_use.input`, which we then validate with Pydantic. We never regex a
   free-text completion for a number - that is exactly how a hallucinated
   amount would leak into a payment.

2. No payment tools. The tool list passed to the model contains *only* schemas
   for producing judgements (which product, which bundle, why). There is no
   `create_order` tool, no `charge` tool, no HTTP escape hatch. The model
   physically cannot call Razorpay because no such capability is ever put in
   front of it.

When ANTHROPIC_API_KEY is unset the client reports `live=False` and every
caller falls back to a deterministic rule-based implementation, so the full
system runs end-to-end with no third-party credentials.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class LLMResult:
    """Structured tool-call output plus which path produced it."""

    data: dict[str, Any]
    mode: str  # "anthropic" | "deterministic"
    error: str | None = None


class LLMClient:
    def __init__(self) -> None:
        self._client = None
        self._live = settings.llm_live_mode
        if self._live:
            try:
                import anthropic

                self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            except Exception as exc:  # pragma: no cover - depends on env
                logger.warning("Anthropic client unavailable, falling back: %s", exc)
                self._live = False

    @property
    def live(self) -> bool:
        return self._live and self._client is not None

    def structured_call(
        self,
        *,
        system: str,
        prompt: str,
        tool_name: str,
        tool_description: str,
        input_schema: dict,
        max_tokens: int = 1024,
    ) -> LLMResult:
        """Force a single structured tool call and return its validated input dict.

        Any failure - no key, network error, malformed response - returns
        mode="deterministic" so the caller applies its rule-based path. The
        system never blocks on, or trusts, model availability.
        """
        if not self.live:
            return LLMResult(data={}, mode="deterministic", error="llm_not_configured")

        try:
            response = self._client.messages.create(
                model=settings.anthropic_model,
                max_tokens=max_tokens,
                system=system,
                tools=[
                    {
                        "name": tool_name,
                        "description": tool_description,
                        "input_schema": input_schema,
                    }
                ],
                # force the model to answer through the schema, not prose
                tool_choice={"type": "tool", "name": tool_name},
                messages=[{"role": "user", "content": prompt}],
            )
            for block in response.content:
                if getattr(block, "type", None) == "tool_use":
                    return LLMResult(data=dict(block.input), mode="anthropic")
            return LLMResult(data={}, mode="deterministic", error="no_tool_use_block")
        except Exception as exc:  # pragma: no cover - depends on network
            logger.warning("LLM call failed, using deterministic fallback: %s", exc)
            return LLMResult(data={}, mode="deterministic", error=str(exc))


_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
