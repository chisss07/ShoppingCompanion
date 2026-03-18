"""
Amazon source adapter via SerpAPI.

Uses SerpAPI's ``amazon`` engine to fetch organic product results directly
from Amazon search, including Prime eligibility and customer ratings.

Docs: https://serpapi.com/amazon-search-api
"""

from __future__ import annotations

import re

import httpx
import structlog

from app.sources.base import BaseSourceAdapter, RawProductListing

logger = structlog.get_logger(__name__)

_SERPAPI_URL = "https://serpapi.com/search.json"


def _parse_price(price_str: str) -> float | None:
    """Parse a price string like '$1,299.99' into a float."""
    if not price_str:
        return None
    cleaned = re.sub(r"[^\d.]", "", str(price_str).replace(",", ""))
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_shipping(delivery: str | None) -> float | None:
    """
    Convert Amazon's delivery string to a shipping cost float.

    'FREE delivery' or 'FREE Returns' → 0.0
    '$5.99 delivery' → 5.99
    None or unrecognised → None (unknown)
    """
    if not delivery:
        return None
    lower = delivery.lower()
    if "free" in lower:
        return 0.0
    match = re.search(r"\$([\d.]+)", delivery)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    return None


class AmazonAdapter(BaseSourceAdapter):
    """
    Fetches Amazon product results via SerpAPI's amazon engine.

    Uses the same SERPAPI_KEY as the Google Shopping adapter — no
    additional credentials required.

    Args:
        api_key: SerpAPI API key.
    """

    name = "Amazon"
    timeout = 12.0  # Amazon pages can be slower than Google Shopping

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def search(
        self,
        keywords: list[str],
        max_price: float | None = None,
    ) -> list[RawProductListing]:
        """
        Query Amazon via SerpAPI for each keyword.

        Only the first keyword is used (Amazon search is comprehensive enough
        that additional keywords produce heavily overlapping results and waste
        API credits).

        Args:
            keywords: Optimised search strings from query understanding.
            max_price: Optional upper price bound for client-side filtering.

        Returns:
            Deduplicated list of normalised Amazon product listings.
        """
        if not keywords:
            return []

        seen_asins: set[str] = set()
        results: list[RawProductListing] = []

        # Use first two keywords at most to avoid burning API credits
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for keyword in keywords[:2]:
                try:
                    listings = await self._fetch_keyword(
                        client, keyword, max_price, seen_asins
                    )
                    results.extend(listings)
                except Exception as exc:
                    logger.warning(
                        "serpapi_amazon_keyword_failed",
                        keyword=keyword,
                        error=str(exc),
                    )

        logger.info("serpapi_amazon_search_complete", result_count=len(results))
        return results

    async def _fetch_keyword(
        self,
        client: httpx.AsyncClient,
        keyword: str,
        max_price: float | None,
        seen_asins: set[str],
    ) -> list[RawProductListing]:
        """Fetch Amazon organic results for a single keyword."""
        params: dict[str, str | int] = {
            "engine": "amazon",
            "k": keyword,
            "api_key": self._api_key,
            "amazon_domain": "amazon.com",
        }

        response = await client.get(_SERPAPI_URL, params=params)
        response.raise_for_status()
        data = response.json()

        listings: list[RawProductListing] = []
        for item in data.get("organic_results", []):
            asin = item.get("asin", "")
            url = item.get("link", "")

            # Deduplicate by ASIN (most reliable Amazon identifier)
            dedup_key = asin or url
            if not dedup_key or dedup_key in seen_asins:
                continue
            seen_asins.add(dedup_key)

            # Price: prefer extracted_price (already a float), fall back to parsing
            price = item.get("extracted_price") or _parse_price(
                str(item.get("price", ""))
            )
            if price is None:
                continue

            # Apply max_price filter client-side (SerpAPI Amazon doesn't support it)
            if max_price is not None and price > max_price:
                continue

            # Rating is on 0-5 scale; convert to 0-100 for our schema
            rating_raw = item.get("rating")
            seller_rating: float | None = None
            if rating_raw is not None:
                try:
                    seller_rating = float(rating_raw) * 20
                except (ValueError, TypeError):
                    pass

            shipping_cost = _parse_shipping(item.get("delivery"))

            # Build a canonical Amazon URL from ASIN if the link isn't absolute
            if asin and (not url or not url.startswith("http")):
                url = f"https://www.amazon.com/dp/{asin}"

            listings.append(
                RawProductListing(
                    source_name="Amazon",
                    product_title=item.get("title", ""),
                    price=price,
                    currency="USD",
                    url=url,
                    availability="in_stock",
                    seller_name="Amazon",
                    seller_rating=seller_rating,
                    image_url=item.get("thumbnail"),
                    shipping_cost=shipping_cost,
                    condition="new",
                    raw_metadata={
                        "asin": asin,
                        "is_prime": item.get("is_prime", False),
                        "reviews": item.get("reviews"),
                        "position": item.get("position"),
                    },
                )
            )

        return listings

    async def health_check(self) -> bool:
        """Verify SerpAPI Amazon engine is reachable."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    _SERPAPI_URL,
                    params={
                        "engine": "amazon",
                        "k": "test",
                        "api_key": self._api_key,
                    },
                )
                return response.status_code == 200
        except Exception:
            return False
