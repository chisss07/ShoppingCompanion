"""
Best Buy Products API source adapter.

Docs: https://bestbuyapis.github.io/api-documentation/#products-api

The adapter queries the Best Buy Products API with each keyword string,
deduplicates by SKU, and returns normalised ``RawProductListing`` objects.
"""

from __future__ import annotations

import re
import structlog

import httpx

from app.sources.base import BaseSourceAdapter, RawProductListing

logger = structlog.get_logger(__name__)

_BASE_URL = "https://api.bestbuy.com/v1/products"


def _parse_availability(online_available: bool) -> str:
    """Map Best Buy's boolean availability flag to our standard string."""
    return "in_stock" if online_available else "out_of_stock"


def _build_search_expression(keyword: str, max_price: float | None) -> str:
    """
    Build a Best Buy products search expression string.

    Best Buy's API uses a Lucene-style expression syntax:
        search=KEYWORD&(condition=new)
    We add a price filter when max_price is specified.
    """
    parts = [f"search={keyword}"]
    if max_price is not None:
        parts.append(f"(salePrice<={max_price:.2f})")
    return "&".join(parts)


class BestBuySourceAdapter(BaseSourceAdapter):
    """
    Fetches product listings from the Best Buy Products API.

    Args:
        api_key: Best Buy developer API key.
    """

    name = "BestBuy"

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def search(
        self,
        keywords: list[str],
        max_price: float | None = None,
    ) -> list[RawProductListing]:
        """
        Search Best Buy for each keyword and return deduplicated results.

        Args:
            keywords: 1-3 optimised search strings.
            max_price: Optional upper price bound in USD.

        Returns:
            Deduplicated list of normalised product listings.
        """
        seen_skus: set[str] = set()
        results: list[RawProductListing] = []

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for keyword in keywords:
                try:
                    listings = await self._fetch_keyword(
                        client, keyword, max_price, seen_skus
                    )
                    results.extend(listings)
                except Exception as exc:
                    logger.warning(
                        "bestbuy_keyword_failed",
                        keyword=keyword,
                        error=str(exc),
                    )

        logger.info("bestbuy_search_complete", result_count=len(results))
        return results

    async def _fetch_keyword(
        self,
        client: httpx.AsyncClient,
        keyword: str,
        max_price: float | None,
        seen_skus: set[str],
    ) -> list[RawProductListing]:
        """Fetch one page of results for a single keyword."""
        params: dict[str, str | int] = {
            "format": "json",
            "sort": "relevance.asc",
            "pageSize": 10,
            "apiKey": self._api_key,
            "show": (
                "sku,name,salePrice,onlineAvailability,url,customerReviewAverage,"
                "freeShipping,manufacturer,modelNumber,thumbnailImage,condition"
            ),
        }
        if max_price is not None:
            params["salePrice"] = f"[* TO {max_price:.2f}]"

        search_expr = keyword.replace(" ", "+")
        url = f"{_BASE_URL}({search_expr})"

        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        listings: list[RawProductListing] = []
        for product in data.get("products", []):
            sku = str(product.get("sku", ""))
            if not sku or sku in seen_skus:
                continue
            seen_skus.add(sku)

            price_raw = product.get("salePrice")
            if price_raw is None:
                continue
            try:
                price = float(price_raw)
            except (TypeError, ValueError):
                continue

            shipping_cost = 0.0 if product.get("freeShipping") else None

            listings.append(
                RawProductListing(
                    source_name=self.name,
                    product_title=product.get("name", ""),
                    price=price,
                    currency="USD",
                    url=product.get("url", ""),
                    availability=_parse_availability(
                        bool(product.get("onlineAvailability"))
                    ),
                    seller_name="Best Buy",
                    seller_rating=float(product.get("customerReviewAverage") or 0) * 20,
                    image_url=product.get("thumbnailImage"),
                    shipping_cost=shipping_cost,
                    condition=product.get("condition", "new").lower(),
                    model_number=product.get("modelNumber"),
                    brand=product.get("manufacturer"),
                    raw_metadata={"sku": sku},
                )
            )

        return listings

    async def health_check(self) -> bool:
        """Ping the Best Buy API with a trivial query to verify reachability."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    _BASE_URL,
                    params={
                        "format": "json",
                        "pageSize": 1,
                        "apiKey": self._api_key,
                    },
                )
                return response.status_code == 200
        except Exception:
            return False
