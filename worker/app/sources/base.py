"""
Abstract base classes and shared data structures for shopping source adapters.

Every adapter returns a list of ``RawProductListing`` objects. The caller
(``SourceManager``) combines them, and ``price_ranker`` scores them.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class RawProductListing:
    """
    Normalised product listing returned by any source adapter.

    All monetary values are in the currency indicated by ``currency``.
    Unknown or unavailable fields should be left as ``None`` rather than
    guessed.

    Attributes:
        source_name: Human-readable adapter name (e.g. "BestBuy", "eBay").
        product_title: Full product title as returned by the source.
        price: Listed price (sale price preferred over MSRP).
        currency: ISO 4217 currency code, default "USD".
        url: Canonical product page URL.
        availability: One of "in_stock", "limited", "preorder", "out_of_stock".
        seller_name: Marketplace seller or retailer name when applicable.
        seller_rating: Numeric seller rating (0-100 scale).
        image_url: Primary product image URL.
        shipping_cost: Flat shipping cost; ``None`` if unknown, 0.0 if free.
        condition: "new", "used", or "refurbished".
        model_number: Manufacturer model / SKU identifier.
        brand: Manufacturer brand name.
        raw_metadata: Source-specific extra fields for debugging / enrichment.
    """

    source_name: str
    product_title: str
    price: float
    currency: str
    url: str
    availability: str
    seller_name: str | None = None
    seller_rating: float | None = None
    image_url: str | None = None
    shipping_cost: float | None = None
    condition: str = "new"
    model_number: str | None = None
    brand: str | None = None
    raw_metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialise to a plain dict suitable for JSON transport."""
        return {
            "source_name": self.source_name,
            "product_title": self.product_title,
            "price": self.price,
            "currency": self.currency,
            "url": self.url,
            "availability": self.availability,
            "seller_name": self.seller_name,
            "seller_rating": self.seller_rating,
            "image_url": self.image_url,
            "shipping_cost": self.shipping_cost,
            "condition": self.condition,
            "model_number": self.model_number,
            "brand": self.brand,
            "raw_metadata": self.raw_metadata or {},
        }


class BaseSourceAdapter(ABC):
    """
    Abstract base class for all shopping source adapters.

    Subclasses implement ``search()`` to query their respective API/scraper
    and return normalised ``RawProductListing`` objects. The
    ``health_check()`` method is used by the maintenance task to monitor
    adapter availability.

    Attributes:
        name: Unique human-readable adapter identifier.
        timeout: Per-request timeout in seconds.
    """

    name: str
    timeout: float = 8.0

    @abstractmethod
    async def search(
        self,
        keywords: list[str],
        max_price: float | None = None,
    ) -> list[RawProductListing]:
        """
        Execute a product search against the underlying data source.

        The adapter should iterate over ``keywords`` (2-3 optimised search
        strings from query understanding) and return deduplicated results.
        Errors should be caught internally and logged; the method must always
        return a list (possibly empty) rather than raise.

        Args:
            keywords: Optimised search strings from query understanding.
            max_price: Optional upper price bound to pass to the API.

        Returns:
            List of normalised product listings, possibly empty.
        """

    async def health_check(self) -> bool:
        """
        Verify the adapter's upstream service is reachable.

        The default implementation always returns True. Adapters that can
        perform a cheap liveness ping should override this method.

        Returns:
            True if the source is healthy, False otherwise.
        """
        return True
