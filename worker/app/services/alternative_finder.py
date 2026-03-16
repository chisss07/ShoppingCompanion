"""
Alternative product finder: use Claude to identify related and competing models.

Given the top-ranked product and all listings from the search, Claude is asked
to surface 2-4 genuine alternatives — successors, competitors, budget options,
or predecessors — that the user should be aware of before making a purchase
decision.

Retry policy:
    Up to 3 attempts on ``APIError`` with exponential back-off (1 s, 2 s).
"""

from __future__ import annotations

import json
import re

import structlog
from anthropic import APIError, AsyncAnthropic
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = structlog.get_logger(__name__)

_SYSTEM_PROMPT = """You are a consumer electronics and product expert helping shoppers
make informed purchase decisions.

Given a target product and a list of related products found during a search, identify
2-4 genuine alternatives the shopper should consider.

For each alternative, assess:
- Whether it is a newer generation / successor (successor)
- Whether it is a direct competitor from another brand (competitor)
- Whether it is a more affordable option (budget_alternative)
- Whether it is an older / previous generation (predecessor)

IMPORTANT: Respond with valid JSON ONLY. No markdown, no explanation.

Return this exact schema:
[
  {
    "product_name": "full product name",
    "model_relationship": "successor|competitor|budget_alternative|predecessor",
    "comparison_summary": "2-3 sentence comparison to the target product",
    "key_differences": [
      {"attribute": "Battery Life", "target": "30 hours", "alternative": "24 hours"}
    ],
    "price_min": 199.99,
    "price_max": 249.99,
    "recommendation_strength": "strong|moderate|weak"
  }
]"""


def _build_user_prompt(
    query: str,
    top_product: dict,
    all_listings: list[dict],
) -> str:
    """
    Build the user message for Claude's alternatives analysis.

    Args:
        query: Original user search query.
        top_product: The highest-ranked product listing dict.
        all_listings: All collected product listing dicts.

    Returns:
        Formatted user prompt string.
    """
    # Summarise all_listings to avoid hitting token limits
    other_products: list[str] = []
    seen_titles: set[str] = set()

    for listing in all_listings:
        title = listing.get("product_title", "")
        if title and title != top_product.get("product_title") and title not in seen_titles:
            price = listing.get("price", "unknown")
            source = listing.get("source_name", "unknown")
            other_products.append(f"- {title} (${price} from {source})")
            seen_titles.add(title)

    other_section = (
        "\n".join(other_products[:20]) if other_products else "No other products found."
    )

    return (
        f"User query: {query!r}\n\n"
        f"Top-ranked product:\n"
        f"  Name: {top_product.get('product_title', 'unknown')}\n"
        f"  Brand: {top_product.get('brand', 'unknown')}\n"
        f"  Price: ${top_product.get('price', 'unknown')}\n"
        f"  Model: {top_product.get('model_number', 'unknown')}\n\n"
        f"Other products found in search:\n{other_section}\n\n"
        f"Identify 2-4 genuine alternatives to the top-ranked product."
    )


@retry(
    retry=retry_if_exception_type(APIError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    reraise=True,
)
async def _call_claude(
    query: str,
    top_product: dict,
    all_listings: list[dict],
    client: AsyncAnthropic,
) -> str:
    """Call Claude and return the raw response text (retried on APIError)."""
    message = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        temperature=0,
        system=_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": _build_user_prompt(query, top_product, all_listings),
            }
        ],
    )
    for block in message.content:
        if block.type == "text":
            return block.text
    return "[]"


def _extract_json_array(raw: str) -> list:
    """
    Extract a JSON array from Claude's response, stripping any markdown fences.

    Args:
        raw: Raw Claude response text.

    Returns:
        Parsed list.

    Raises:
        ValueError: If no valid JSON array is found.
    """
    cleaned = re.sub(r"```(?:json)?", "", raw).strip()

    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        pass

    # Try to extract first [...] block
    match = re.search(r"\[.*\]", cleaned, re.DOTALL)
    if match:
        return json.loads(match.group())

    raise ValueError(f"No valid JSON array in response: {raw[:200]!r}")


def _normalise_alternative(raw: dict) -> dict:
    """
    Coerce a raw alternative dict into the expected schema with safe defaults.
    """
    valid_relationships = {"successor", "competitor", "budget_alternative", "predecessor"}
    valid_strengths = {"strong", "moderate", "weak"}

    relationship = str(raw.get("model_relationship", "competitor")).lower()
    if relationship not in valid_relationships:
        relationship = "competitor"

    strength = str(raw.get("recommendation_strength", "moderate")).lower()
    if strength not in valid_strengths:
        strength = "moderate"

    price_min = raw.get("price_min")
    price_max = raw.get("price_max")

    return {
        "product_name": str(raw.get("product_name", "")),
        "model_relationship": relationship,
        "comparison_summary": str(raw.get("comparison_summary", "")),
        "key_differences": list(raw.get("key_differences", [])),
        "price_min": float(price_min) if price_min is not None else None,
        "price_max": float(price_max) if price_max is not None else None,
        "recommendation_strength": strength,
    }


async def identify_alternatives(
    query: str,
    top_product: dict,
    all_listings: list[dict],
    anthropic_client: AsyncAnthropic,
) -> list[dict]:
    """
    Use Claude to identify 2-4 alternative products for the top search result.

    Alternatives may be newer generations, direct competitors, budget options,
    or predecessor models. Each is returned with a structured comparison to
    help the user make an informed choice.

    Args:
        query: Original user search query.
        top_product: The highest-ranked product listing dict (with deal_score).
        all_listings: All product listing dicts collected from all sources.
        anthropic_client: Configured ``AsyncAnthropic`` client instance.

    Returns:
        List of 2-4 alternative product dicts conforming to the schema:
        ``product_name``, ``model_relationship``, ``comparison_summary``,
        ``key_differences``, ``price_min``, ``price_max``,
        ``recommendation_strength``.

        Returns an empty list on any failure rather than raising, so the
        search pipeline can continue without alternatives.
    """
    log = logger.bind(query=query, top_product=top_product.get("product_title"))
    log.info("alternative_finder_start")

    try:
        raw_response = await _call_claude(
            query, top_product, all_listings, anthropic_client
        )
        log.debug("alternative_finder_raw_response", response=raw_response[:500])

        raw_alternatives = _extract_json_array(raw_response)
        alternatives = [_normalise_alternative(a) for a in raw_alternatives[:4]]

        log.info("alternative_finder_complete", count=len(alternatives))
        return alternatives

    except Exception as exc:
        log.error(
            "alternative_finder_failed",
            error=str(exc),
            exc_info=True,
        )
        return []
