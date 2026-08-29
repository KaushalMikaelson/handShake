"""Natural-language goal -> ParsedIntent (US-2).

The LLM path is preferred; the deterministic path below is the fallback and is
good enough to run the whole demo without credentials. Both produce the same
Pydantic model, so downstream code cannot tell (or care) which ran.

Critically, neither path is allowed to invent a budget. If the user gave no
spending limit, `needs_clarification` is set and the agent asks - it never
silently assumes one.
"""
from __future__ import annotations

import re

from app.agents.llm import get_llm_client
from app.schemas.agents import ParsedIntent
from app.services.money import to_paise

INTENT_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {
            "type": "string",
            "description": "Product category, e.g. 'electronics' or 'accessories'.",
        },
        "budget_max": {
            "type": "integer",
            "description": (
                "Maximum total the user is willing to spend, in PAISE "
                "(multiply rupees by 100). Omit entirely if the user gave no budget."
            ),
        },
        "preferred_brands": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Brands the user named a preference for. Empty if none.",
        },
        "use_case": {
            "type": "string",
            "description": "Short phrase describing what they need it for.",
        },
        "require_approval_above": {
            "type": "integer",
            "description": (
                "In PAISE. If the user said something like 'ask me before spending "
                "more than X', put X here. Omit if they said nothing about approval."
            ),
        },
        "needs_clarification": {
            "type": "boolean",
            "description": "True if a budget was not stated and must be asked for.",
        },
        "clarification_question": {
            "type": "string",
            "description": "The single question to ask the user, if clarification is needed.",
        },
    },
    "required": ["needs_clarification"],
}

SYSTEM_PROMPT = (
    "You extract structured shopping intent from a user's message for an autonomous "
    "buying agent that operates under strict spending policy. Money must always be "
    "expressed in paise (rupees x 100). Never invent a budget the user did not state: "
    "if no spending limit is given, set needs_clarification to true and ask for one. "
    "You are only extracting intent - you never select products or authorise spending."
)

_CATEGORY_KEYWORDS = {
    "electronics": [
        "headphone", "headphones", "earphone", "earbuds", "speaker", "laptop",
        "phone", "electronics", "audio", "tws",
    ],
    "accessories": ["case", "cable", "cover", "pouch", "adapter", "accessory", "accessories"],
}

_KNOWN_BRANDS = ["sony", "boat", "sennheiser", "jbl", "bose", "audiohub", "samsung", "apple"]

# "10,000" / "10k" / "1.5 lakh" / "₹8999"
_AMOUNT_RE = re.compile(
    r"(?:rs\.?|inr|₹)?\s*(\d[\d,]*(?:\.\d+)?)\s*(k|thousand|lakh|lakhs|l)?\b",
    re.IGNORECASE,
)
_UNDER_RE = re.compile(
    r"(under|below|less than|within|upto|up to|max(?:imum)?(?: of)?|budget of|not more than)"
    r"\s*(?:rs\.?|inr|₹)?\s*(\d[\d,]*(?:\.\d+)?)\s*(k|thousand|lakh|lakhs|l)?",
    re.IGNORECASE,
)
_APPROVAL_RE = re.compile(
    r"(?:don'?t|do not|never)\s+spend\s+(?:more than|over|above)\s*(?:rs\.?|inr|₹)?\s*"
    r"(\d[\d,]*(?:\.\d+)?)\s*(k|thousand|lakh|lakhs|l)?"
    r"|(?:ask|check with|confirm with)\s+me\s+(?:before|above|over|beyond)\s*"
    r"(?:spending\s*)?(?:rs\.?|inr|₹)?\s*(\d[\d,]*(?:\.\d+)?)\s*(k|thousand|lakh|lakhs|l)?",
    re.IGNORECASE,
)


def _scale(raw: str, suffix: str | None) -> int:
    """Convert a matched rupee figure + magnitude suffix into paise."""
    value = float(raw.replace(",", ""))
    s = (suffix or "").lower()
    if s in {"k", "thousand"}:
        value *= 1_000
    elif s in {"lakh", "lakhs", "l"}:
        value *= 100_000
    return to_paise(value)


def _classify_category(lowered: str) -> str | None:
    """Pick the category of the thing being BOUGHT, not merely mentioned.

    "an aux cable for my headphones" is an accessories purchase even though it
    names a headphone: the object of the purchase is normally named first, so we
    rank by earliest keyword position and break ties on hit count.
    """
    best: tuple[int, int, str] | None = None
    for cat, keywords in _CATEGORY_KEYWORDS.items():
        positions = [lowered.find(k) for k in keywords if k in lowered]
        if not positions:
            continue
        candidate = (min(positions), -len(positions), cat)
        if best is None or candidate < best:
            best = candidate
    return best[2] if best else None


def parse_intent_deterministic(query: str) -> ParsedIntent:
    text = query.strip()
    lowered = text.lower()

    category = _classify_category(lowered)

    approval = None
    m = _APPROVAL_RE.search(text)
    if m:
        if m.group(1):
            approval = _scale(m.group(1), m.group(2))
        elif m.group(3):
            approval = _scale(m.group(3), m.group(4))

    budget = None
    m = _UNDER_RE.search(text)
    if m:
        budget = _scale(m.group(2), m.group(3))
    else:
        # fall back to the largest bare figure in the message, ignoring one we
        # already consumed as an approval threshold
        candidates = [
            _scale(g[0], g[1])
            for g in _AMOUNT_RE.findall(text)
            if g[0].strip(",.")
        ]
        candidates = [c for c in candidates if c >= 10_000 and c != approval]
        if candidates:
            budget = max(candidates)

    brands = [b.capitalize() for b in _KNOWN_BRANDS if b in lowered]
    # "boat" -> "boAt" as the catalog spells it
    brands = ["boAt" if b.lower() == "boat" else b for b in brands]

    needs_clarification = budget is None
    return ParsedIntent(
        category=category,
        budget_max=budget,
        preferred_brands=brands,
        use_case=text[:200],
        require_approval_above=approval,
        needs_clarification=needs_clarification,
        clarification_question=(
            "What is the maximum you want to spend on this? I will not proceed "
            "without an explicit budget."
            if needs_clarification
            else None
        ),
    )


def parse_intent(query: str) -> tuple[ParsedIntent, str]:
    """Return (intent, mode). Falls back to deterministic parsing on any LLM issue."""
    client = get_llm_client()
    result = client.structured_call(
        system=SYSTEM_PROMPT,
        prompt=f"Extract the shopping intent from this message:\n\n{query}",
        tool_name="record_shopping_intent",
        tool_description="Record the structured shopping intent extracted from the user message.",
        input_schema=INTENT_TOOL_SCHEMA,
    )
    if result.mode == "anthropic" and result.data:
        try:
            # Pydantic validation at the boundary is what makes trusting this safe
            parsed = ParsedIntent.model_validate(result.data)
            if parsed.budget_max is None:
                parsed.needs_clarification = True
                parsed.clarification_question = (
                    parsed.clarification_question
                    or "What is the maximum you want to spend on this?"
                )
            return parsed, "anthropic"
        except Exception:  # malformed structured output -> deterministic path
            pass
    return parse_intent_deterministic(query), "deterministic"
