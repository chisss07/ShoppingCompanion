"""
Mock source adapter for development and testing.

Returns realistic-looking product listings without making any real API calls.
This adapter is always registered by ``SourceManager`` so the UI has something
meaningful to render even when no API keys are configured.

Product data is loosely modelled after a real Sony WH-1000XM5 search to give
a varied and believable result set covering multiple retailers, prices, and
availability states.
"""

from __future__ import annotations

import asyncio
import random
from copy import deepcopy

from app.sources.base import BaseSourceAdapter, RawProductListing

# ---------------------------------------------------------------------------
# Fixture data — five realistic listings for the "headphones" category
# ---------------------------------------------------------------------------
_MOCK_LISTINGS: list[dict] = [
    {
        "source_name": "MockStore",
        "product_title": "Sony WH-1000XM5 Wireless Noise Canceling Headphones - Black",
        "price": 279.99,
        "currency": "USD",
        "url": "https://mockstore.example.com/products/sony-wh1000xm5-black",
        "availability": "in_stock",
        "seller_name": "MockStore",
        "seller_rating": 92.0,
        "image_url": "https://via.placeholder.com/400x400.png?text=Sony+WH-1000XM5",
        "shipping_cost": 0.0,
        "condition": "new",
        "model_number": "WH1000XM5/B",
        "brand": "Sony",
        "raw_metadata": {"is_mock": True, "retailer": "MockStore"},
    },
    {
        "source_name": "MockMarket",
        "product_title": "Sony WH-1000XM5 Headphones - Silver (International Version)",
        "price": 259.00,
        "currency": "USD",
        "url": "https://mockmarket.example.com/item/sony-wh1000xm5-silver",
        "availability": "limited",
        "seller_name": "AudioDeals_Mock",
        "seller_rating": 74.0,
        "image_url": "https://via.placeholder.com/400x400.png?text=Sony+WH-1000XM5+Silver",
        "shipping_cost": 9.99,
        "condition": "new",
        "model_number": "WH1000XM5/S",
        "brand": "Sony",
        "raw_metadata": {"is_mock": True, "retailer": "MockMarket"},
    },
    {
        "source_name": "MockBuy",
        "product_title": "Sony WH-1000XM5 Wireless Headphones Bundle with Carrying Case",
        "price": 319.99,
        "currency": "USD",
        "url": "https://mockbuy.example.com/listing/wh1000xm5-bundle",
        "availability": "in_stock",
        "seller_name": "MockBuy Official",
        "seller_rating": 88.0,
        "image_url": "https://via.placeholder.com/400x400.png?text=Sony+Bundle",
        "shipping_cost": 0.0,
        "condition": "new",
        "model_number": "WH1000XM5/B",
        "brand": "Sony",
        "raw_metadata": {"is_mock": True, "retailer": "MockBuy", "bundle": True},
    },
    {
        "source_name": "MockElectronics",
        "product_title": "Bose QuietComfort 45 Wireless Headphones - Triple Black",
        "price": 249.00,
        "currency": "USD",
        "url": "https://mockelectronics.example.com/bose-qc45-black",
        "availability": "in_stock",
        "seller_name": "MockElectronics",
        "seller_rating": 95.0,
        "image_url": "https://via.placeholder.com/400x400.png?text=Bose+QC45",
        "shipping_cost": 0.0,
        "condition": "new",
        "model_number": "866724-0100",
        "brand": "Bose",
        "raw_metadata": {"is_mock": True, "retailer": "MockElectronics"},
    },
    {
        "source_name": "MockWarehouse",
        "product_title": "Apple AirPods Max - Midnight (USB-C) Wireless Over-Ear Headphones",
        "price": 449.00,
        "currency": "USD",
        "url": "https://mockwarehouse.example.com/airpods-max-midnight",
        "availability": "preorder",
        "seller_name": "MockWarehouse",
        "seller_rating": 85.0,
        "image_url": "https://via.placeholder.com/400x400.png?text=AirPods+Max",
        "shipping_cost": 0.0,
        "condition": "new",
        "model_number": "MQTP3LL/A",
        "brand": "Apple",
        "raw_metadata": {"is_mock": True, "retailer": "MockWarehouse"},
    },
]


class MockSourceAdapter(BaseSourceAdapter):
    """
    Mock shopping source adapter.

    Returns a copy of the fixture listings with slight price jitter applied
    so rankings look realistic across multiple test runs. A small artificial
    delay simulates real network I/O.

    This adapter is always enabled and requires no API key.
    """

    name = "Mock"
    timeout = 8.0

    async def search(
        self,
        keywords: list[str],
        max_price: float | None = None,
    ) -> list[RawProductListing]:
        """
        Return fixture product listings with optional price filtering.

        Args:
            keywords: Ignored — mock data is keyword-independent.
            max_price: When set, listings above this price are excluded.

        Returns:
            Up to 5 realistic mock product listings.
        """
        # Simulate network latency (100-300 ms)
        await asyncio.sleep(random.uniform(0.1, 0.3))

        results: list[RawProductListing] = []
        for raw in deepcopy(_MOCK_LISTINGS):
            # Apply ±5% random jitter so prices vary across invocations
            raw["price"] = round(raw["price"] * random.uniform(0.95, 1.05), 2)

            if max_price is not None and raw["price"] > max_price:
                continue

            results.append(
                RawProductListing(
                    source_name=raw["source_name"],
                    product_title=raw["product_title"],
                    price=raw["price"],
                    currency=raw["currency"],
                    url=raw["url"],
                    availability=raw["availability"],
                    seller_name=raw.get("seller_name"),
                    seller_rating=raw.get("seller_rating"),
                    image_url=raw.get("image_url"),
                    shipping_cost=raw.get("shipping_cost"),
                    condition=raw.get("condition", "new"),
                    model_number=raw.get("model_number"),
                    brand=raw.get("brand"),
                    raw_metadata=raw.get("raw_metadata", {}),
                )
            )

        return results

    async def health_check(self) -> bool:
        """Mock adapter is always healthy."""
        return True
