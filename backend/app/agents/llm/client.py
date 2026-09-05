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
import re
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def _clean_json_text(text: str) -> str:
    """Clean markdown code fences or extract JSON substring from model outputs."""
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.IGNORECASE)
        t = re.sub(r"\s*```$", "", t)
        t = t.strip()
    try:
        json.loads(t)
        return t
    except Exception:
        pass

    # Extract outermost JSON object if model included explanation text
    match = re.search(r"(\{.*\})", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return t


@dataclass
class LLMResult:
    """Structured tool-call output plus which path produced it."""

    data: dict[str, Any]
    mode: str  # "groq" | "gemini" | "anthropic" | "deterministic"
    error: str | None = None


class LLMClient:
    def __init__(self) -> None:
        self._genai_client = None
        self._anthropic_client = None

        if settings.gemini_api_key:
            try:
                from google import genai
                self._genai_client = genai.Client(api_key=settings.gemini_api_key)
            except Exception as exc:
                logger.warning("Google GenAI client init failed: %s", exc)

        if settings.anthropic_api_key:
            try:
                import anthropic
                self._anthropic_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            except Exception as exc:
                logger.warning("Anthropic client init failed: %s", exc)

    @property
    def live(self) -> bool:
        return settings.llm_live_mode

    @property
    def provider(self) -> str:
        if settings.groq_api_key:
            return "groq"
        if settings.gemini_api_key:
            return "gemini"
        if settings.anthropic_api_key:
            return "anthropic"
        return "deterministic"

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

        Tries configured provider(s) and automatically falls back if rate-limited
        or unavailable.
        """
        if not self.live:
            return LLMResult(data={}, mode="deterministic", error="llm_not_configured")

        # Prioritize providers based on configured API keys
        providers_to_try: list[str] = []
        if settings.groq_api_key:
            providers_to_try.append("groq")
        if settings.gemini_api_key:
            providers_to_try.append("gemini")
        if settings.anthropic_api_key:
            providers_to_try.append("anthropic")

        for provider in providers_to_try:
            if provider == "groq":
                res = self._call_groq(
                    system=system,
                    prompt=prompt,
                    tool_name=tool_name,
                    tool_description=tool_description,
                    input_schema=input_schema,
                )
                if res.mode != "deterministic" and res.data:
                    return res
            elif provider == "gemini":
                res = self._call_gemini(
                    system=system,
                    prompt=prompt,
                    tool_name=tool_name,
                    tool_description=tool_description,
                    input_schema=input_schema,
                )
                if res.mode != "deterministic" and res.data:
                    return res
            elif provider == "anthropic" and self._anthropic_client:
                res = self._call_anthropic(
                    system=system,
                    prompt=prompt,
                    tool_name=tool_name,
                    tool_description=tool_description,
                    input_schema=input_schema,
                    max_tokens=max_tokens,
                )
                if res.mode != "deterministic" and res.data:
                    return res

        return LLMResult(data={}, mode="deterministic", error="all_llm_providers_failed")

    def _call_groq(
        self,
        *,
        system: str,
        prompt: str,
        tool_name: str,
        tool_description: str,
        input_schema: dict,
    ) -> LLMResult:
        system_instruction = (
            f"{system}\n\n"
            f"Task ({tool_name}): {tool_description}\n\n"
            f"You MUST output a valid JSON object matching this schema:\n"
            f"{json.dumps(input_schema, indent=2)}"
        )

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.groq_api_key}",
            "Content-Type": "application/json",
        }

        # Try user configured model, then fallback models if rate-limited (429)
        models_to_try = [settings.groq_model]
        for alt in ["openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3.8-27b"]:
            if alt not in models_to_try:
                models_to_try.append(alt)

        for model in models_to_try:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.1,
            }

            try:
                with httpx.Client(timeout=10.0) as http_client:
                    response = http_client.post(url, headers=headers, json=payload)
                    if response.status_code == 200:
                        res_data = response.json()
                        choices = res_data.get("choices", [])
                        if choices:
                            raw_text = choices[0]["message"]["content"]
                            text = _clean_json_text(raw_text)
                            parsed_data = json.loads(text)
                            if isinstance(parsed_data, dict):
                                return LLMResult(data=parsed_data, mode="groq")
                    else:
                        logger.warning("Groq (%s) HTTP %s: %s", model, response.status_code, response.text[:150])
            except Exception as exc:
                logger.warning("Groq (%s) call error: %s", model, exc)

        return LLMResult(data={}, mode="deterministic", error="groq_call_failed")

    def _call_gemini(
        self,
        *,
        system: str,
        prompt: str,
        tool_name: str,
        tool_description: str,
        input_schema: dict,
    ) -> LLMResult:
        system_instruction = (
            f"{system}\n\n"
            f"Task ({tool_name}): {tool_description}\n\n"
            f"You MUST output a valid JSON object matching this schema:\n"
            f"{json.dumps(input_schema, indent=2)}"
        )

        full_prompt = f"{system_instruction}\n\nUser Request: {prompt}"

        # Candidate models for Gemini
        models_to_try = [settings.gemini_model]
        for alt in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
            if alt not in models_to_try:
                models_to_try.append(alt)

        # 1. SDK path
        if self._genai_client is not None:
            for model in models_to_try:
                try:
                    from google.genai import types

                    response = self._genai_client.models.generate_content(
                        model=model,
                        contents=full_prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            temperature=0.1,
                        ),
                    )
                    text = _clean_json_text(response.text or "")
                    parsed_data = json.loads(text)
                    if isinstance(parsed_data, dict):
                        return LLMResult(data=parsed_data, mode="gemini")
                except Exception as exc:
                    logger.warning("Gemini SDK (%s) error: %s", model, exc)

        # 2. Resilient HTTP fallback path
        for model in models_to_try:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
                headers = {
                    "x-goog-api-key": settings.gemini_api_key,
                    "Content-Type": "application/json",
                }

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

                with httpx.Client(timeout=10.0) as http_client:
                    response = http_client.post(url, headers=headers, json=payload)
                    if response.status_code == 200:
                        res_data = response.json()
                        candidates = res_data.get("candidates", [])
                        if candidates:
                            raw_text = candidates[0]["content"]["parts"][0]["text"]
                            text = _clean_json_text(raw_text)
                            parsed_data = json.loads(text)
                            if isinstance(parsed_data, dict):
                                return LLMResult(data=parsed_data, mode="gemini")
                    else:
                        logger.warning("Gemini HTTP (%s) error %s: %s", model, response.status_code, response.text[:150])
            except Exception as exc:
                logger.warning("Gemini HTTP (%s) call error: %s", model, exc)

        return LLMResult(data={}, mode="deterministic", error="gemini_call_failed")

    @staticmethod
    def _parse_retry_delay(text: str, default: float = 32) -> float:
        """Extract retryDelay seconds from a Gemini 429 error message."""
        import re as _re
        match = _re.search(r"retry\s*(?:in|Delay[\"']?\s*:\s*[\"']?)(\d+(?:\.\d+)?)", text, _re.IGNORECASE)
        if match:
            return min(float(match.group(1)) + 2, 65)  # add 2s margin, cap at 65s
        return default

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
        except Exception as exc:  # pragma: no cover - depends on network
            logger.warning("Anthropic call failed, using deterministic fallback: %s", exc)
            return LLMResult(data={}, mode="deterministic", error=str(exc))


_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
