"""
Pydantic v2 request/response schemas for the search and history APIs.

All schemas use strict typing and validators to ensure clean data flows
between the HTTP boundary and the database / Celery pipeline.

Schema hierarchy:
    Request:
        SearchRequest          -- POST /api/v1/search body
    Response (search):
        SearchSessionResponse  -- 202 immediately after POST
        SearchStatusResponse   -- GET /api/v1/search/{id}
        PriceEntry             -- one row in the comparison table
        Alternative            -- one alternative product
        SummaryDict            -- structured summary block
        SearchResultsResponse  -- GET /api/v1/search/{id}/results (full payload)
    Response (history):
        HistoryItem            -- one row in the history list
        HistoryResponse        -- paginated list of HistoryItem
    Common:
        ErrorDetail            -- standard error body
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class SearchRequest(BaseModel):
    """Request body for POST /api/v1/search."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description=(
            "Natural-language product search query. "
            "Supports brand names, model numbers, and descriptive attributes."
        ),
        examples=["Sony WH-1000XM5 headphones", "best noise cancelling headphones under 300"],
    )
    max_price: Optional[float] = Field(
        default=None,
        gt=0,
        description="Upper price limit in USD. Omit to search without a price ceiling.",
    )
    min_sources: int = Field(
        default=3,
        ge=1,
        le=10,
        description=(
            "Minimum number of sources that must return results before the pipeline "
            "proceeds to ranking. If fewer sources respond, the pipeline widens the "
            "search keywords and tries a second round."
        ),
    )
    include_alternatives: bool = Field(
        default=True,
        description=(
            "When True, Stage 5 (alternative model identification) is executed. "
            "Set to False to skip alternatives and reduce total search latency by ~3s."
        ),
    )

    @field_validator("query")
    @classmethod
    def strip_query(cls, v: str) -> str:
        """Strip leading/trailing whitespace from the query."""
        return v.strip()


# ---------------------------------------------------------------------------
# Search session response schemas
# ---------------------------------------------------------------------------

class SearchSessionResponse(BaseModel):
    """
    Returned immediately after POST /api/v1/search (HTTP 202 Accepted).

    The client should connect to websocket_url to receive real-time progress
    events and then poll GET /api/v1/search/{session_id}/results once the
    'complete' WebSocket event fires.
    """

    model_config = ConfigDict(from_attributes=True)

    session_id: uuid.UUID
    status: str
    websocket_url: str = Field(
        description="Relative WebSocket URL the client should connect to for progress events.",
        examples=["/ws/search/a1b2c3d4-e5f6-7890-abcd-ef1234567890"],
    )
    estimated_duration_seconds: int = Field(
        default=15,
        description="Rough estimate of how many seconds until results are ready.",
    )


class SearchStatusResponse(BaseModel):
    """Returned by GET /api/v1/search/{session_id}."""

    model_config = ConfigDict(from_attributes=True)

    session_id: uuid.UUID
    status: str
    query_text: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    result_count: Optional[int] = None
    total_sources_queried: Optional[int] = None


# ---------------------------------------------------------------------------
# Results schemas
# ---------------------------------------------------------------------------

class PriceEntry(BaseModel):
    """
    One ranked product listing in the comparison table.

    Returned inside SearchResultsResponse.comparison as a list ordered by rank.
    """

    model_config = ConfigDict(from_attributes=True)

    rank: int
    source: str = Field(description="Human-readable source name, e.g. 'Amazon', 'Best Buy'.")
    product_title: str
    price: float
    shipping: Optional[str] = Field(
        default=None,
        description="Shipping cost as a display string, e.g. 'Free (Prime)' or '$9.99'.",
    )
    availability: str
    seller_rating: Optional[float] = None
    condition: str
    deal_score: Optional[float] = None
    url: str
    image_url: Optional[str] = None
    brand: Optional[str] = None
    model_number: Optional[str] = None


class Alternative(BaseModel):
    """One AI-identified alternative product."""

    model_config = ConfigDict(from_attributes=True)

    product_name: str
    model_relationship: str = Field(
        description="One of: successor, predecessor, competitor, budget_alternative.",
    )
    comparison_summary: str
    key_differences: list[Any] = Field(
        default_factory=list,
        description=(
            "List of spec comparison objects. "
            "Each: {attribute: str, target: str, alternative: str}."
        ),
    )
    price_range: Optional[dict[str, Any]] = Field(
        default=None,
        description="{'min': float, 'max': float} from live source queries.",
    )
    recommendation_strength: str = Field(
        description="One of: strong, moderate, weak.",
    )
    source_urls: list[str] = Field(default_factory=list)


class SummaryDict(BaseModel):
    """Structured summary block embedded in SearchResultsResponse."""

    top_pick: str = Field(description="3-4 sentence summary of the top recommendation.")
    alternatives_brief: Optional[str] = None
    caveats: Optional[str] = None
    model_version: str = Field(description="Claude model that generated this summary.")
    generated_at: datetime
    token_usage: dict[str, Any] = Field(default_factory=dict)


class SearchResultsResponse(BaseModel):
    """
    Full results payload returned by GET /api/v1/search/{session_id}/results.

    HTTP 200 when status='complete', HTTP 202 when still processing.
    """

    model_config = ConfigDict(from_attributes=True)

    session_id: uuid.UUID
    query: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    summary: Optional[SummaryDict] = None
    comparison: list[PriceEntry] = Field(default_factory=list)
    alternatives: list[Alternative] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# History schemas
# ---------------------------------------------------------------------------

class HistoryItem(BaseModel):
    """One row in the search history list."""

    model_config = ConfigDict(from_attributes=True)

    session_id: uuid.UUID
    query_text: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    result_count: Optional[int] = None
    best_price: Optional[float] = Field(
        default=None,
        description="Price of the rank=1 result at search time.",
    )
    best_source: Optional[str] = Field(
        default=None,
        description="Source name for the rank=1 result.",
    )


class HistoryResponse(BaseModel):
    """Paginated response for GET /api/v1/history."""

    items: list[HistoryItem]
    total: int = Field(description="Total number of history records matching the filter.")
    page: int
    limit: int


# ---------------------------------------------------------------------------
# Common / error schemas
# ---------------------------------------------------------------------------

class ErrorDetail(BaseModel):
    """Standard error response body, consistent with the architecture spec."""

    code: str = Field(description="Machine-readable error code, e.g. 'SEARCH_TIMEOUT'.")
    message: str = Field(description="Human-readable error message.")
    detail: Optional[str] = Field(default=None, description="Additional context.")
    session_id: Optional[uuid.UUID] = None
    recoverable: bool = False


class ErrorResponse(BaseModel):
    """Wrapper for ErrorDetail to match the spec's {error: {...}} envelope."""

    error: ErrorDetail
