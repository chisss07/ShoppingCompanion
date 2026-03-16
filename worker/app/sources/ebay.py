"""
eBay Browse API source adapter.

Uses the eBay Browse API (v1) to search for new-condition items on the US
marketplace. OAuth token is passed directly; token refresh is out of scope
for this adapter (the token is expected to be long-lived or rotated via an
external secret manager).

Docs: https://developer.ebay.com/api-docs/buy/browse/resources/item_summary/methods/search
"""

from __future__ import annotations

import structlog

import httpx

from app.sources.base import BaseSourceAdapter, RawProductListing

logger = structlog.get_logger(__name__)

_BROWSE_API_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"


def _parse_availability(buying_options: list[str]) -> str:
    """Map eBay buying options to our standard availability string."""
    if not buying_options:
        return "in_stock"
    opts = {o.upper() for o in buying_options}
    if "FIXED_PRICE" in opts or "BUY_IT_NOW" in opts:
        return "in_stock"
    return "in_stock"


def _parse_price(price_obj: dict | None) -> float | None:
    """Extract a float price from an eBay price object like {"value": "799.99", "currency": "USD"}."""
    if not price_obj:
        return None
    try:
        return float(price_obj.get("value", 0))
    except (TypeError, ValueError):
        return None


class EbaySourceAdapter(BaseSourceAdapter):
    """
    Fetches new-condition product listings from eBay via the Browse API.

    Args:
        oauth_token: eBay OAuth 2.0 Application Token (Bearer).
    """

    name = "eBay"

    def __init__(self, oauth_token: str) -> None:
        self._token = oauth_token

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
            "Content-Type": "application/json",
        }

    async def search(
        self,
        keywords: list[str],
        max_price: float | None = None,
    ) -> list[RawProductListing]:
        """
        Search eBay for new-condition items matching each keyword.

        Args:
            keywords: Optimised search strings from query understanding.
            max_price: Optional upper price bound in USD.

        Returns:
            Deduplicated list of normalised product listings.
        """
        seen_ids: set[str] = set()
        results: list[RawProductListing] = []

        async with httpx.AsyncClient(
            headers=self._headers, timeout=self.timeout
        ) as client:
            for keyword in keywords:
                try:
                    listings = await self._fetch_keyword(
                        client, keyword, max_price, seen_ids
                    )
                    results.extend(listings)
                except Exception as exc:
                    logger.warning(
                        "ebay_keyword_failed",
                        keyword=keyword,
                        error=str(exc),
                    )

        logger.info("ebay_search_complete", result_count=len(results))
        return results

    async def _fetch_keyword(
        self,
        client: httpx.AsyncClient,
        keyword: str,
        max_price: float | None,
        seen_ids: set[str],
    ) -> list[RawProductListing]:
        """Fetch eBay listings for a single keyword."""
        params: dict[str, str | int] = {
            "q": keyword,
            "limit": 10,
            "filter": "conditions:{NEW}",
            "sort": "bestMatch",
        }
        if max_price is not None:
            params["filter"] = f"conditions:{{NEW}},price:[..{max_price:.2f}],priceCurrency:USD"

        response = await client.get(_BROWSE_API_URL, params=params)
        response.raise_for_status()
        data = response.json()

        listings: list[RawProductListing] = []
        for item in data.get("itemSummaries", []):
            item_id = item.get("itemId", "")
            if not item_id or item_id in seen_ids:
                continue
            seen_ids.add(item_id)

            price = _parse_price(item.get("price"))
            if price is None:
                continue

            # Seller feedback percentage (0-100)
            seller_info = item.get("seller", {})
            feedback_pct_raw = seller_info.get("feedbackPercentage")
            seller_rating: float | None = None
            if feedback_pct_raw is not None:
                try:
                    seller_rating = float(feedback_pct_raw)
                except (TypeError, ValueError):
                    seller_rating = None

            # Thumbnail image
            thumbnails = item.get("thumbnailImages", [])
            image_url = thumbnails[0].get("imageUrl") if thumbnails else None

            # Shipping cost
            shipping_options = item.get("shippingOptions", [])
            shipping_cost: float | None = None
            if shipping_options:
                ship_cost_obj = shipping_options[0].get("shippingCost", {})
                if ship_cost_obj.get("value") == "0.00" or ship_cost_obj.get("value") == "0":
                    shipping_cost = 0.0
                elif ship_cost_obj.get("value"):
                    try:
                        shipping_cost = float(ship_cost_obj["value"])
                    except (TypeError, ValueError):
                        shipping_cost = None

            listings.append(
                RawProductListing(
                    source_name=self.name,
                    product_title=item.get("title", ""),
                    price=price,
                    currency=item.get("price", {}).get("currency", "USD"),
                    url=item.get("itemWebUrl", ""),
                    availability=_parse_availability(
                        item.get("buyingOptions", [])
                    ),
                    seller_name=seller_info.get("username"),
                    seller_rating=seller_rating,
                    image_url=image_url,
                    shipping_cost=shipping_cost,
                    condition="new",
                    raw_metadata={
                        "item_id": item_id,
                        "feedback_score": seller_info.get("feedbackScore"),
                        "buying_options": item.get("buyingOptions"),
                    },
                )
            )

        return listings

    async def health_check(self) -> bool:
        """Verify eBay Browse API is reachable."""
        try:
            async with httpx.AsyncClient(
                headers=self._headers, timeout=5.0
            ) as client:
                response = await client.get(
                    _BROWSE_API_URL,
                    params={"q": "test", "limit": 1, "filter": "conditions:{NEW}"},
                )
                # 200 OK or 400 (bad request on minimal params) both indicate connectivity
                return response.status_code in {200, 400}
        except Exception:
            return False
