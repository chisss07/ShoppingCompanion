"""
Query understanding service: parse raw user queries with Claude.

Claude returns a structured JSON payload that the search pipeline uses to
generate optimised keyword strings, apply price filters, and focus scraping
on the most relevant product attributes.

Retry policy:
    Up to 3 attempts on Anthropic ``APIError`` with exponential back-off
    (1 s, 2 s). Non-retryable errors (authentication, invalid request) are
    re-raised immediately.
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

_SYSTEM_PROMPT = """You are a shopping query parser. Your sole job is to extract
structured information from a user's natural-language product search query.

IMPORTANT: Respond with valid JSON ONLY. No markdown, no explanation, no code
fences — just the raw JSON object.

Return this exact schema:
{
  "product_category": "string — broad category, e.g. 'headphones', 'laptop', 'coffee maker'",
  "key_attributes": ["list of important attributes the user cares about, e.g. 'noise canceling', 'wireless'"],
  "brand_preference": "string or null — specific brand if mentioned",
  "price_ceiling": "number or null — maximum price in USD if mentioned",
  "search_keywords": ["2-3 optimised search strings ready to submit to retailer APIs"],
  "model_hints": ["list of specific model names or numbers mentioned, empty if none"]
}"""

_USER_PROMPT_TEMPLATE = 'Parse this shopping query: "{query}"'


@retry(
    retry=retry_if_exception_type(APIError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    reraise=True,
)
async def _call_claude(query: str, client: AsyncAnthropic) -> str:
    """
    Send the query to Claude and return the raw response text.

    Decorated with tenacity to retry on transient ``APIError`` exceptions.
    """
    message = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        temperature=0,
        system=_SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": _USER_PROMPT_TEMPLATE.format(query=query)}
        ],
    )
    # Extract text from the first content block
    for block in message.content:
        if block.type == "text":
            return block.text
    return ""


def _extract_json(raw: str) -> dict:
    """
    Extract a JSON object from Claude's response.

    Handles the common case where Claude wraps output in markdown fences
    despite the system prompt explicitly prohibiting it.

    Args:
        raw: Raw string returned by Claude.

    Returns:
        Parsed dictionary.

    Raises:
        ValueError: If no valid JSON object can be extracted.
    """
    # Strip markdown fences if present
    cleaned = re.sub(r"```(?:json)?", "", raw).strip()

    # Attempt direct parse first
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Fall back to extracting the first {...} block
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        return json.loads(match.group())

    raise ValueError(f"No valid JSON found in Claude response: {raw[:200]!r}")


async def parse_query(query: str, anthropic_client: AsyncAnthropic) -> dict:
    """
    Call Claude to extract structured information from a user's search query.

    The returned payload is used by the search pipeline to:
    - Build optimised keyword strings for retailer API calls
    - Apply price ceiling filters
    - Focus result ranking on user-relevant attributes

    Args:
        query: Raw natural-language product search query from the user.
        anthropic_client: Configured ``AsyncAnthropic`` client instance.

    Returns:
        Dictionary with keys:
            - ``product_category`` (str): Broad product category.
            - ``key_attributes`` (list[str]): User-relevant attributes.
            - ``brand_preference`` (str | None): Preferred brand or None.
            - ``price_ceiling`` (float | None): Max price in USD or None.
            - ``search_keywords`` (list[str]): 2-3 optimised search strings.
            - ``model_hints`` (list[str]): Specific model numbers mentioned.

    Raises:
        APIError: After exhausting retries on transient Anthropic errors.
        ValueError: If Claude returns unparseable output.
    """
    log = logger.bind(query=query)
    log.info("query_understanding_start")

    raw_response = await _call_claude(query, anthropic_client)
    log.debug("query_understanding_raw_response", response=raw_response[:500])

    parsed = _extract_json(raw_response)

    # Normalise and fill defaults for any missing keys
    result: dict = {
        "product_category": str(parsed.get("product_category", "unknown")),
        "key_attributes": list(parsed.get("key_attributes", [])),
        "brand_preference": parsed.get("brand_preference") or None,
        "price_ceiling": (
            float(parsed["price_ceiling"])
            if parsed.get("price_ceiling") is not None
            else None
        ),
        "search_keywords": list(parsed.get("search_keywords", [query])),
        "model_hints": list(parsed.get("model_hints", [])),
    }

    # Ensure we always have at least one keyword
    if not result["search_keywords"]:
        result["search_keywords"] = [query]

    log.info(
        "query_understanding_complete",
        category=result["product_category"],
        keyword_count=len(result["search_keywords"]),
        price_ceiling=result["price_ceiling"],
    )
    return result
