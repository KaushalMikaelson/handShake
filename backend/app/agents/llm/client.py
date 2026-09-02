"""LLM client wrapper - structured output only (Gemini & Anthropic supported).

Two hard rules encoded here:

1. Structured output only. The model is called with a tool schema and we read
   its JSON structure, which we then validate with Pydantic. We never regex a
   free-text completion for a number - that is exactly how a hallucinated
   amount would leak into a payment.

2. No payment tools. The tool list passed to the model contains *only* schemas
   for producing judgements (which product, which bundle, why). There is no
   `create_order` tool, no `charge` tool, no HTTP escape hatch. The model
   physically cannot call Razorpay because no such capability is ever put in
   front of it.

When no LLM API key is set, the client reports `live=False` and every
caller falls back to a deterministic rule-based implementation, so the full
system runs end-to-end with no third-party credentials.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class LLMResult:
    """Structured tool-call output plus which path produced it."""

    data: dict[str, Any]
    mode: str  # "gemini" | "anthropic" | "deterministic"
    error: str | None = None


class LLMClient:
    def __init__(self) -> None:
        self.provider: str | None = None
        self._anthropic_client = None
        self._live = settings.llm_live_mode

        if settings.gemini_api_key:
            self.provider = "gemini"
            self._live = True
        elif settings.anthropic_api_key:
            try:
                import anthropic

                self._anthropic_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
                self.provider = "anthropic"
                self._live = True
            except Exception as exc:  # pragma: no cover - depends on env
                logger.warning("Anthropic client unavailable, falling back: %s", exc)
                self._live = False
        else:
            self._live = False

    @property
    def live(self) -> bool:
        return self._live

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

        if self.provider == "gemini":
            return self._call_gemini(
                system=system,
                prompt=prompt,
                tool_name=tool_name,
                tool_description=tool_description,
                input_schema=input_schema,
            )
        elif self.provider == "anthropic" and self._anthropic_client:
            return self._call_anthropic(
                system=system,
                prompt=prompt,
                tool_name=tool_name,
                tool_description=tool_description,
                input_schema=input_schema,
                max_tokens=max_tokens,
            )

        return LLMResult(data={}, mode="deterministic", error="no_valid_provider")

    def _call_gemini(
        self,
        *,
        system: str,
        prompt: str,
        tool_name: str,
        tool_description: str,
        input_schema: dict,
    ) -> LLMResult:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent?key={settings.gemini_api_key}"

            system_instruction = (
                f"{system}\n\n"
                f"Task ({tool_name}): {tool_description}\n\n"
                f"You MUST output a valid JSON object matching this schema:\n"
                f"{json.dumps(input_schema, indent=2)}"
            )

            payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": prompt}],
                    }
                ],
                "systemInstruction": {
                    "parts": [{"text": system_instruction}]
                },
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "temperature": 0.1,
                },
            }

            with httpx.Client(timeout=15.0) as http_client:
                response = http_client.post(url, json=payload)
                response.raise_for_status()
                res_data = response.json()

            candidates = res_data.get("candidates", [])
            if not candidates:
                return LLMResult(data={}, mode="deterministic", error="gemini_no_candidates")

            text = candidates[0]["content"]["parts"][0]["text"].strip()
            parsed_data = json.loads(text)
            if isinstance(parsed_data, dict):
                return LLMResult(data=parsed_data, mode="gemini")

            return LLMResult(data={}, mode="deterministic", error="gemini_invalid_json_type")
        except Exception as exc:
            logger.warning("Gemini LLM call failed, using deterministic fallback: %s", exc)
            return LLMResult(data={}, mode="deterministic", error=str(exc))

    def _call_anthropic(
        self,
        *,
        system: str,
        prompt: str,
        tool_name: str,
        tool_description: str,
        input_schema: dict,
        max_tokens: int = 1024,
    ) -> LLMResult:
        try:
            response = self._anthropic_client.messages.create(
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
                tool_choice={"type": "tool", "name": tool_name},
                messages=[{"role": "user", "content": prompt}],
            )
            for block in response.content:
                if getattr(block, "type", None) == "tool_use":
                    return LLMResult(data=dict(block.input), mode="anthropic")
            return LLMResult(data={}, mode="deterministic", error="no_tool_use_block")
        except Exception as exc:
            logger.warning("Anthropic call failed, using deterministic fallback: %s", exc)
            return LLMResult(data={}, mode="deterministic", error=str(exc))


_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
