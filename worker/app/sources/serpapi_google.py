"""
Google Shopping source adapter via SerpAPI.

SerpAPI proxies Google Shopping results and handles rendering, CAPTCHAs, and
geographic rotation. We use the ``google_shopping`` engine.

Docs: https://serpapi.com/google-shopping-api
"""

from __future__ import annotations

import re

import httpx
import structlog

from app.sources.base import BaseSourceAdapter, RawProductListing

logger = structlog.get_logger(__name__)

_SERPAPI_URL = "https://serpapi.com/search.json"

# Retailer name normalisation: map SerpAPI source strings to our canonical names
_SOURCE_NAME_MAP: dict[str, str] = {
    "amazon.com": "Amazon",
    "amazon": "Amazon",
    "bestbuy.com": "BestBuy",
    "best buy": "BestBuy",
    "walmart.com": "Walmart",
    "walmart": "Walmart",
    "target.com": "Target",
    "target": "Target",
    "ebay.com": "eBay",
    "ebay": "eBay",
    "costco.com": "Costco",
    "newegg.com": "Newegg",
    "bhphotovideo.com": "B&H Photo",
}


def _normalise_source(raw_source: str) -> str:
    """Map a raw SerpAPI source string to a canonical retailer name."""
    lower = raw_source.lower().strip()
    return _SOURCE_NAME_MAP.get(lower, raw_source.strip().title())


def _parse_price(price_str: str) -> float | None:
    """
    Parse a price string like "$1,299.99" or "1299.99" into a float.

    Returns None if parsing fails.
    """
    if not price_str:
        return None
    cleaned = re.sub(r"[^\d.]", "", price_str.replace(",", ""))
    try:
        return float(cleaned)
    except ValueError:
        return None


class GoogleShoppingAdapter(BaseSourceAdapter):
    """
    Fetches Google Shopping results via SerpAPI.

    Each keyword triggers one SerpAPI request. Results are deduplicated by
    product URL.

    Args:
        api_key: SerpAPI API key.
    """

    name = "GoogleShopping"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def search(
        self,
        keywords: list[str],
        max_price: float | None = None,
    ) -> list[RawProductListing]:
        """
        Query Google Shopping via SerpAPI for each keyword.

        Args:
            keywords: Optimised search strings from query understanding.
            max_price: Optional upper price bound (passed as ``price_to`` param).

        Returns:
            Deduplicated list of normalised product listings.
        """
        seen_urls: set[str] = set()
        results: list[RawProductListing] = []

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for keyword in keywords:
                try:
                    listings = await self._fetch_keyword(
                        client, keyword, max_price, seen_urls
                    )
                    results.extend(listings)
                except Exception as exc:
                    logger.warning(
                        "serpapi_keyword_failed",
                        keyword=keyword,
                        error=str(exc),
                    )

        logger.info("serpapi_search_complete", result_count=len(results))
        return results

    async def _fetch_keyword(
        self,
        client: httpx.AsyncClient,
        keyword: str,
        max_price: float | None,
        seen_urls: set[str],
    ) -> list[RawProductListing]:
        """Fetch Google Shopping results for a single keyword."""
        params: dict[str, str | int] = {
            "engine": "google_shopping",
            "q": keyword,
            "api_key": self._api_key,
            "gl": "us",
            "hl": "en",
            "num": 10,
        }
        if max_price is not None:
            params["price_to"] = int(max_price)

        response = await client.get(_SERPAPI_URL, params=params)
        response.raise_for_status()
        data = response.json()

        listings: list[RawProductListing] = []
        for item in data.get("shopping_results", []):
            url = item.get("link", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            price_raw = item.get("price", "")
            price = _parse_price(str(price_raw))
            if price is None:
                continue

            source_name = _normalise_source(item.get("source", "Unknown"))

            # SerpAPI sometimes provides rating as "4.5 out of 5"
            rating_raw = item.get("rating")
            seller_rating: float | None = None
            if rating_raw is not None:
                try:
                    seller_rating = float(str(rating_raw).split()[0]) * 20
                except (ValueError, IndexError):
                    seller_rating = None

            listings.append(
                RawProductListing(
                    source_name=source_name,
                    product_title=item.get("title", ""),
                    price=price,
                    currency="USD",
                    url=url,
                    availability="in_stock",  # SerpAPI doesn't expose availability
                    seller_name=item.get("source"),
                    seller_rating=seller_rating,
                    image_url=item.get("thumbnail"),
                    shipping_cost=None,
                    condition="new",
                    raw_metadata={
                        "position": item.get("position"),
                        "reviews": item.get("reviews"),
                        "extensions": item.get("extensions"),
                    },
                )
            )

        return listings

    async def health_check(self) -> bool:
        """Verify SerpAPI is reachable with a minimal test query."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    _SERPAPI_URL,
                    params={
                        "engine": "google_shopping",
                        "q": "test",
                        "api_key": self._api_key,
                        "num": 1,
                    },
                )
                return response.status_code == 200
        except Exception:
            return False
