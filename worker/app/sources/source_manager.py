"""
Source manager: orchestrates concurrent queries across all configured adapters.

``SourceManager`` holds all enabled adapter instances and provides a single
``search_all()`` coroutine that fans out to every adapter in parallel, collects
results, and fires progress callbacks so the task layer can publish WebSocket
events in real time.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

import structlog

from app.core.config import Settings
from app.sources.base import BaseSourceAdapter, RawProductListing
from app.sources.mock import MockSourceAdapter

logger = structlog.get_logger(__name__)

# Type alias for the async progress callbacks
OnSourceStart = Callable[[str], Coroutine[Any, Any, None]]
OnSourceComplete = Callable[[str, list[RawProductListing], Exception | None], Coroutine[Any, Any, None]]


class SourceManager:
    """
    Manages all source adapters and runs concurrent product searches.

    Adapters are initialised based on which API keys are present in settings.
    The mock adapter is always appended so the system is functional in
    development without any external credentials.

    Args:
        settings: Application settings instance.
    """

    def __init__(self, settings: Settings) -> None:
        self.adapters: list[BaseSourceAdapter] = []
        self._init_adapters(settings)

    def _init_adapters(self, settings: Settings) -> None:
        """Instantiate adapters for every configured API key."""
        # Lazy imports avoid loading unused adapter modules
        if settings.BESTBUY_API_KEY:
            from app.sources.bestbuy import BestBuySourceAdapter
            self.adapters.append(BestBuySourceAdapter(settings.BESTBUY_API_KEY))
            logger.info("source_adapter_enabled", adapter="BestBuy")

        if settings.SERPAPI_KEY:
            from app.sources.serpapi_amazon import AmazonAdapter
            from app.sources.serpapi_google import GoogleShoppingAdapter
            self.adapters.append(GoogleShoppingAdapter(settings.SERPAPI_KEY))
            self.adapters.append(AmazonAdapter(settings.SERPAPI_KEY))
            logger.info("source_adapter_enabled", adapter="GoogleShopping")
            logger.info("source_adapter_enabled", adapter="Amazon")

        if settings.EBAY_OAUTH_TOKEN:
            from app.sources.ebay import EbaySourceAdapter
            self.adapters.append(EbaySourceAdapter(settings.EBAY_OAUTH_TOKEN))
            logger.info("source_adapter_enabled", adapter="eBay")

        # Mock adapter is only used as a fallback when no real sources are configured.
        # In production with API keys set, real adapters run exclusively.
        if not self.adapters:
            self.adapters.append(MockSourceAdapter())
            logger.warning(
                "source_manager_no_real_adapters",
                fallback="mock",
                hint="Set SERPAPI_KEY, BESTBUY_API_KEY, or EBAY_OAUTH_TOKEN to enable real search",
            )

        logger.info(
            "source_manager_ready",
            adapter_count=len(self.adapters),
            adapters=[a.name for a in self.adapters],
        )

    async def search_all(
        self,
        keywords: list[str],
        max_price: float | None,
        on_source_start: OnSourceStart,
        on_source_complete: OnSourceComplete,
    ) -> list[RawProductListing]:
        """
        Run all adapters concurrently and collect their results.

        For each adapter the method:
        1. Calls ``on_source_start(adapter.name)`` before issuing the query.
        2. Awaits the adapter's ``search()`` with an 8-second timeout.
        3. Calls ``on_source_complete(adapter.name, results, error)`` after.

        Individual adapter failures are caught and reported via the callback
        rather than propagated, so a single broken source never aborts the
        entire search.

        Args:
            keywords: Optimised search strings from query understanding.
            max_price: Optional price ceiling to pass to each adapter.
            on_source_start: Async callback fired before each adapter query.
            on_source_complete: Async callback fired after each adapter query.

        Returns:
            Combined list of all listings from all adapters.
        """
        tasks = [
            self._run_adapter(
                adapter, keywords, max_price, on_source_start, on_source_complete
            )
            for adapter in self.adapters
        ]

        per_adapter_results: list[list[RawProductListing]] = await asyncio.gather(
            *tasks, return_exceptions=False
        )

        all_listings: list[RawProductListing] = [
            listing
            for adapter_listings in per_adapter_results
            for listing in adapter_listings
        ]

        logger.info(
            "source_manager_search_complete",
            total_listings=len(all_listings),
            adapters_queried=len(self.adapters),
        )
        return all_listings

    async def _run_adapter(
        self,
        adapter: BaseSourceAdapter,
        keywords: list[str],
        max_price: float | None,
        on_source_start: OnSourceStart,
        on_source_complete: OnSourceComplete,
    ) -> list[RawProductListing]:
        """
        Run a single adapter with timeout and error isolation.

        Args:
            adapter: The adapter to query.
            keywords: Search strings to pass through.
            max_price: Optional price ceiling.
            on_source_start: Callback to fire before the search.
            on_source_complete: Callback to fire after the search.

        Returns:
            Listings from this adapter, or empty list on failure/timeout.
        """
        await on_source_start(adapter.name)

        results: list[RawProductListing] = []
        error: Exception | None = None

        try:
            results = await asyncio.wait_for(
                adapter.search(keywords, max_price),
                timeout=adapter.timeout,
            )
            logger.info(
                "adapter_search_success",
                adapter=adapter.name,
                result_count=len(results),
            )
        except asyncio.TimeoutError as exc:
            error = exc
            logger.warning("adapter_search_timeout", adapter=adapter.name, timeout=adapter.timeout)
        except Exception as exc:
            error = exc
            logger.error(
                "adapter_search_error",
                adapter=adapter.name,
                error=str(exc),
                exc_info=True,
            )

        await on_source_complete(adapter.name, results, error)
        return results

    async def health_check_all(self) -> dict[str, bool]:
        """
        Run health checks on all adapters concurrently.

        Returns:
            Mapping of adapter name to health status boolean.
        """
        async def check(adapter: BaseSourceAdapter) -> tuple[str, bool]:
            try:
                healthy = await asyncio.wait_for(adapter.health_check(), timeout=5.0)
            except Exception:
                healthy = False
            return adapter.name, healthy

        results = await asyncio.gather(*[check(a) for a in self.adapters])
        return dict(results)
