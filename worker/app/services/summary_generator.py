"""
Summary generation service: Claude writes a human-readable comparison summary.

The summary is generated with streaming so the caller can observe progress,
then the complete text is assembled and returned as a structured dict.

Streaming is used here for two reasons:
1. Summary generation is the longest LLM call (~800 tokens output).
2. Future versions can forward streamed chunks over the WebSocket channel.

Retry policy:
    Up to 3 attempts on ``APIError`` with exponential back-off (1 s, 2 s).
"""

from __future__ import annotations

import structlog
from anthropic import APIError, AsyncAnthropic
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = structlog.get_logger(__name__)

_SYSTEM_PROMPT = """You are a knowledgeable and impartial shopping assistant helping
consumers find the best deals.

Write a concise, helpful comparison summary for the search results. Be specific
about prices, sellers, and key trade-offs. Do not use bullet points — write in
flowing prose paragraphs.

Structure your response EXACTLY as three sections separated by the delimiters below:

---TOP_PICK---
3-4 sentences recommending the best deal and explaining why.

---ALTERNATIVES---
2-3 sentences briefly summarising the alternative options and who they suit.

---CAVEATS---
1-2 sentences with any important warnings (price volatility, unknown sellers,
limited availability). Write "None" if there are no significant caveats."""


def _build_user_prompt(
    query: str,
    ranked_listings: list[dict],
    alternatives: list[dict],
) -> str:
    """
    Build the user message for summary generation.

    Keeps the prompt compact by limiting to the top 5 listings and 3 alternatives.
    """
    top_listings = ranked_listings[:5]

    listings_text_parts: list[str] = []
    for i, listing in enumerate(top_listings, start=1):
        shipping = (
            "Free shipping"
            if listing.get("shipping_cost") == 0.0
            else f"${listing.get('shipping_cost', '?')} shipping"
            if listing.get("shipping_cost") is not None
            else "Shipping unknown"
        )
        listings_text_parts.append(
            f"{i}. {listing.get('product_title', 'Unknown')} | "
            f"${listing.get('price', '?')} from {listing.get('source_name', '?')} | "
            f"{listing.get('availability', 'unknown')} | "
            f"{shipping} | "
            f"Deal score: {listing.get('deal_score', '?')}"
        )
    listings_text = "\n".join(listings_text_parts)

    alt_parts: list[str] = []
    for alt in alternatives[:3]:
        alt_parts.append(
            f"- {alt.get('product_name', '?')} "
            f"({alt.get('model_relationship', '?')}, "
            f"strength: {alt.get('recommendation_strength', '?')})"
        )
    alternatives_text = "\n".join(alt_parts) if alt_parts else "None identified."

    return (
        f"User searched for: {query!r}\n\n"
        f"Top ranked products:\n{listings_text}\n\n"
        f"Identified alternatives:\n{alternatives_text}\n\n"
        "Write the comparison summary."
    )


def _parse_sections(text: str) -> tuple[str, str, str | None]:
    """
    Parse the three-section structured output from Claude.

    Args:
        text: Full assembled response text.

    Returns:
        Tuple of (top_pick_summary, alternatives_brief, caveats | None).
    """
    sections: dict[str, str] = {}
    current_key: str | None = None
    current_lines: list[str] = []

    for line in text.splitlines():
        stripped = line.strip()
        if stripped == "---TOP_PICK---":
            if current_key:
                sections[current_key] = " ".join(current_lines).strip()
            current_key = "top_pick"
            current_lines = []
        elif stripped == "---ALTERNATIVES---":
            if current_key:
                sections[current_key] = " ".join(current_lines).strip()
            current_key = "alternatives"
            current_lines = []
        elif stripped == "---CAVEATS---":
            if current_key:
                sections[current_key] = " ".join(current_lines).strip()
            current_key = "caveats"
            current_lines = []
        elif current_key:
            current_lines.append(stripped)

    if current_key and current_lines:
        sections[current_key] = " ".join(current_lines).strip()

    top_pick = sections.get("top_pick") or text.strip()
    alternatives_brief = sections.get("alternatives") or ""
    caveats_raw = sections.get("caveats", "None")
    caveats: str | None = None if (not caveats_raw or caveats_raw.lower() == "none") else caveats_raw

    return top_pick, alternatives_brief, caveats


@retry(
    retry=retry_if_exception_type(APIError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    reraise=True,
)
async def _stream_summary(
    query: str,
    ranked_listings: list[dict],
    alternatives: list[dict],
    client: AsyncAnthropic,
) -> tuple[str, dict]:
    """
    Stream a summary from Claude and return the assembled text plus token usage.

    Returns:
        Tuple of (assembled_text, token_usage_dict).
    """
    user_prompt = _build_user_prompt(query, ranked_listings, alternatives)
    chunks: list[str] = []
    input_tokens = 0
    output_tokens = 0

    async with client.messages.stream(
        model="claude-sonnet-4-6",
        max_tokens=800,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    ) as stream:
        async for text in stream.text_stream:
            chunks.append(text)

        # Final message carries usage statistics
        final_message = await stream.get_final_message()
        input_tokens = final_message.usage.input_tokens
        output_tokens = final_message.usage.output_tokens

    assembled = "".join(chunks)
    token_usage = {"input": input_tokens, "output": output_tokens}
    return assembled, token_usage


async def generate_summary(
    query: str,
    ranked_listings: list[dict],
    alternatives: list[dict],
    anthropic_client: AsyncAnthropic,
) -> dict:
    """
    Call Claude with streaming to generate a structured comparison summary.

    The summary covers the best deal recommendation, a brief on alternatives,
    and any purchase caveats (seller risk, limited stock, etc.).

    Args:
        query: Original user search query.
        ranked_listings: All product listings sorted by deal_score descending.
        alternatives: Alternative products identified by ``identify_alternatives``.
        anthropic_client: Configured ``AsyncAnthropic`` client instance.

    Returns:
        Dictionary with keys:
            - ``top_pick_summary`` (str): 3-4 sentence best deal recommendation.
            - ``alternatives_brief`` (str): 2-3 sentences on alternatives.
            - ``caveats`` (str | None): Warnings about pricing or sellers.
            - ``model_version`` (str): Claude model identifier used.
            - ``token_usage`` (dict): ``{"input": int, "output": int}``.

        Returns a minimal error dict if generation fails rather than raising.
    """
    log = logger.bind(query=query, listing_count=len(ranked_listings))
    log.info("summary_generator_start")

    try:
        assembled_text, token_usage = await _stream_summary(
            query, ranked_listings, alternatives, anthropic_client
        )

        log.debug("summary_generator_raw", text=assembled_text[:300])

        top_pick_summary, alternatives_brief, caveats = _parse_sections(assembled_text)

        result = {
            "top_pick_summary": top_pick_summary,
            "alternatives_brief": alternatives_brief,
            "caveats": caveats,
            "model_version": "claude-sonnet-4-6",
            "token_usage": token_usage,
        }

        log.info(
            "summary_generator_complete",
            input_tokens=token_usage["input"],
            output_tokens=token_usage["output"],
        )
        return result

    except Exception as exc:
        log.error("summary_generator_failed", error=str(exc), exc_info=True)
        return {
            "top_pick_summary": "Unable to generate summary at this time.",
            "alternatives_brief": "",
            "caveats": None,
            "model_version": "claude-sonnet-4-6",
            "token_usage": {"input": 0, "output": 0},
        }
