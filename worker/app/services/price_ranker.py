"""
Price ranking service: compute deal scores and rank product listings.

The scoring model is a weighted sum of five sub-scores, each normalised to
[0.0, 1.0]:

    deal_score = 0.45 * price_score
               + 0.25 * seller_score
               + 0.15 * availability_score
               + 0.10 * shipping_score
               + 0.05 * return_policy_score

Sub-score computation:
    price_score       = 1.0 - (price / max_price_in_set)
    seller_score      = known_reputation / 100
    availability_score: in_stock=1.0, limited=0.7, preorder=0.4, out_of_stock=0.0
    shipping_score    : free=1.0, else 1.0 - min(cost/price, 1.0)
    return_policy_score: not available from current sources, defaults to 0.5

All input listings are expected to be plain dicts (as serialised by
``RawProductListing.to_dict()``). The ranker augments each dict with
``deal_score`` and ``rank`` keys and returns the list sorted descending.
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)

# Weights must sum to 1.0
_WEIGHTS = {
    "price": 0.45,
    "seller": 0.25,
    "availability": 0.15,
    "shipping": 0.10,
    "return_policy": 0.05,
}

# Known retailer reputation scores (out of 100)
_RETAILER_REPUTATION: dict[str, float] = {
    "amazon": 95.0,
    "bestbuy": 92.0,
    "best buy": 92.0,
    "walmart": 88.0,
    "target": 85.0,
    "costco": 87.0,
    "newegg": 80.0,
    "b&h photo": 82.0,
    "ebay": 70.0,
    "googleshopping": 80.0,
    "mock": 80.0,
    "mockstore": 80.0,
    "mockmarket": 75.0,
    "mockbuy": 80.0,
    "mockelectronics": 80.0,
    "mockwarehouse": 80.0,
}

_DEFAULT_REPUTATION = 60.0

_AVAILABILITY_SCORES: dict[str, float] = {
    "in_stock": 1.0,
    "limited": 0.7,
    "preorder": 0.4,
    "out_of_stock": 0.0,
}

# Default return policy score: 0.5 (neutral, unknown policy)
_DEFAULT_RETURN_POLICY_SCORE = 0.5


def _seller_score(listing: dict) -> float:
    """
    Compute a 0-1 seller reputation score for a listing.

    Checks the ``seller_name`` field first, then falls back to
    ``source_name``. If the seller's ``seller_rating`` (0-100) is provided
    and the seller isn't in our known-retailer table, we use the rating
    directly (scaled to [0, 1]).
    """
    source = (listing.get("source_name") or "").lower().strip()
    seller = (listing.get("seller_name") or "").lower().strip()

    # Check known retailer table by seller name, then by source name
    for name in (seller, source):
        if name in _RETAILER_REPUTATION:
            return _RETAILER_REPUTATION[name] / 100.0

    # Fall back to API-provided rating if available
    rating = listing.get("seller_rating")
    if rating is not None:
        try:
            return min(float(rating), 100.0) / 100.0
        except (TypeError, ValueError):
            pass

    return _DEFAULT_REPUTATION / 100.0


def _availability_score(listing: dict) -> float:
    """Return a 0-1 availability score based on the listing's availability string."""
    availability = (listing.get("availability") or "in_stock").lower().strip()
    return _AVAILABILITY_SCORES.get(availability, 0.5)


def _shipping_score(listing: dict) -> float:
    """
    Compute a 0-1 shipping score.

    Free shipping (shipping_cost == 0.0) gets a perfect score. When shipping
    cost is unknown (None) we assume a moderate cost relative to the product
    price, returning 0.6. Otherwise we penalise proportionally.
    """
    shipping_cost = listing.get("shipping_cost")
    price = listing.get("price", 1.0) or 1.0

    if shipping_cost is None:
        # Unknown shipping — conservative neutral score
        return 0.6

    shipping_cost = float(shipping_cost)
    if shipping_cost == 0.0:
        return 1.0

    # Penalise shipping cost relative to product price, capped at -1.0
    penalty = min(shipping_cost / price, 1.0)
    return 1.0 - penalty


def _compute_deal_score(
    listing: dict,
    max_price: float,
) -> float:
    """
    Compute the weighted deal score for a single listing.

    Args:
        listing: Product listing dict (from ``RawProductListing.to_dict()``).
        max_price: Maximum price in the entire candidate set (used for normalisation).

    Returns:
        Deal score in [0.0, 1.0].
    """
    price = float(listing.get("price", 0) or 0)
    price_score = 1.0 - (price / max_price) if max_price > 0 else 0.5

    score = (
        _WEIGHTS["price"] * price_score
        + _WEIGHTS["seller"] * _seller_score(listing)
        + _WEIGHTS["availability"] * _availability_score(listing)
        + _WEIGHTS["shipping"] * _shipping_score(listing)
        + _WEIGHTS["return_policy"] * _DEFAULT_RETURN_POLICY_SCORE
    )

    # Clamp to [0, 1] to guard against floating-point edge cases
    return max(0.0, min(1.0, score))


def rank_listings(listings: list[dict]) -> list[dict]:
    """
    Compute ``deal_score`` for each listing and return them sorted descending.

    The function is pure: it does not mutate the input dicts, returning new
    dict copies with ``deal_score`` and ``rank`` keys added.

    Args:
        listings: List of product listing dicts. Each must contain at least
                  ``price`` (float) and ``availability`` (str).

    Returns:
        New list of listing dicts sorted by ``deal_score`` descending, with
        ``rank`` (1-indexed) and ``deal_score`` (float, 4 dp) added.
    """
    if not listings:
        return []

    # Determine the price ceiling for normalisation (exclude zeros)
    prices = [float(l.get("price", 0) or 0) for l in listings]
    max_price = max(prices) if any(p > 0 for p in prices) else 1.0

    scored: list[dict] = []
    for listing in listings:
        enriched = dict(listing)
        enriched["deal_score"] = round(_compute_deal_score(listing, max_price), 4)
        scored.append(enriched)

    # Sort descending by deal_score, then ascending by price as tie-breaker
    scored.sort(key=lambda l: (-l["deal_score"], l.get("price", 0)))

    for rank, listing in enumerate(scored, start=1):
        listing["rank"] = rank

    logger.info(
        "price_ranker_complete",
        total_listings=len(scored),
        top_score=scored[0]["deal_score"] if scored else None,
        top_source=scored[0].get("source_name") if scored else None,
    )
    return scored
