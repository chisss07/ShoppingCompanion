# Shopping Companion - Architecture Document

**Version:** 1.0  
**Date:** 2026-03-15  
**Status:** Design Phase

---

## Table of Contents

1. System Overview
2. AI/ML Components
3. Data Flow
4. API Design
5. External Data Sources Strategy
6. Service Architecture (Docker Compose)
7. Security and Compliance
8. Scalability and Performance
9. Monitoring and Observability

---

## 1. System Overview

### 1.1 High-Level Architecture

Shopping Companion is a microservices-based web application that uses AI to find the best prices for products across the internet, compare options from multiple reputable sources, and recommend alternative or newer models. The system is fully containerized with Docker Compose and follows an event-driven architecture for real-time search progress updates.

```
                         +-------------------+
                         |   User (Browser)  |
                         +--------+----------+
                                  |
                         HTTP / WebSocket
                                  |
                    +-------------+-------------+
                    |     Nginx Reverse Proxy    |
                    +---+------------------+----+
                        |                  |
              +---------+------+   +-------+---------+
              | Frontend (React|   | WebSocket Server |
              | SPA - Nginx)   |   | (Python/FastAPI) |
              +----------------+   +---------+--------+
                                             |
                                   +---------+---------+
                                   | Backend API       |
                                   | (Python FastAPI)   |
                                   +--+------+------+--+
                                      |      |      |
                              +-------+  +---+---+  +--------+
                              |          |       |           |
                     +--------+--+ +-----+---+ +-+--------+ |
                     | PostgreSQL | |  Redis   | | Celery   | |
                     | Database   | |  Cache   | | Workers  | |
                     +------------+ +----------+ | (AI/Search)|
                                                 +-----+------+
                                                       |
                                            +----------+----------+
                                            | External APIs &     |
                                            | Web Sources         |
                                            +---------------------+
```

### 1.2 Tech Stack Decisions and Justifications

| Layer | Technology | Justification |
|-------|-----------|---------------|
| **Frontend** | React 18 + TypeScript | Component-based UI with strong typing; large ecosystem for UI components; excellent developer tooling. |
| **Frontend State** | Zustand | Lightweight state management; simpler than Redux for this scale; native support for WebSocket-driven state updates. |
| **Frontend Styling** | Tailwind CSS | Utility-first approach accelerates development; consistent design system; small production bundle with purging. |
| **Backend API** | Python 3.12 + FastAPI | Native async support critical for concurrent API/scraping calls; automatic OpenAPI docs; Pydantic validation; Python ecosystem dominance in AI/ML tooling. |
| **Task Queue** | Celery + Redis (broker) | Offloads long-running AI search tasks from the request cycle; supports task chaining for multi-step search pipelines; retry logic built-in. |
| **AI/LLM** | Anthropic Claude API (claude-sonnet-4-20250514) | Strong reasoning for product comparison and model matching; structured output support for reliable data extraction; cost-effective for summarization tasks. |
| **Database** | PostgreSQL 16 | JSONB columns for flexible product data storage; full-text search for historical queries; mature, reliable ACID-compliant store. |
| **Cache** | Redis 7 | Sub-millisecond reads for cached price data; pub/sub for WebSocket event distribution; Celery broker co-location eliminates an extra service. |
| **WebSocket** | FastAPI WebSocket endpoints | Native FastAPI support avoids separate framework; shares authentication with REST layer; backed by Redis pub/sub for horizontal scaling. |
| **Web Scraping** | httpx + BeautifulSoup4 + Playwright | httpx for async HTTP requests to APIs; BeautifulSoup for HTML parsing; Playwright for JavaScript-rendered pages that resist simple HTTP scraping. |
| **Containerization** | Docker Compose | Single-command local development; mirrors production topology; environment variable management via .env files. |
| **Reverse Proxy** | Nginx | SSL termination; static file serving for React SPA; WebSocket upgrade handling; request routing to backend services. |

---

## 2. AI/ML Components

### 2.1 AI Agent Architecture

The AI system is not a single monolithic model but a pipeline of specialized stages, each using the most appropriate technique for its task. The pipeline is orchestrated by Celery task chains.

```
User Query
    |
    v
+-------------------+     +---------------------+     +--------------------+
| Stage 1:          | --> | Stage 2:            | --> | Stage 3:           |
| Query             |     | Multi-Source         |     | Data Extraction    |
| Understanding     |     | Product Search       |     | & Normalization    |
+-------------------+     +---------------------+     +--------------------+
                                                              |
                                                              v
+-------------------+     +---------------------+     +--------------------+
| Stage 6:          | <-- | Stage 5:            | <-- | Stage 4:           |
| Summary           |     | Alternative Model    |     | Price Comparison   |
| Generation        |     | Identification       |     | & Ranking          |
+-------------------+     +---------------------+     +--------------------+
```

### 2.2 Stage 1 - Query Understanding (Claude API)

**Purpose:** Transform a raw user query into a structured product search specification.

**How it works:**

The user's free-text query (e.g., "best noise cancelling headphones under 300") is sent to Claude with a system prompt that instructs it to extract structured fields. Claude returns a JSON object with:

- `product_category` - e.g., "headphones"
- `key_attributes` - e.g., ["noise cancelling", "over-ear"]
- `brand_preference` - e.g., null (none specified)
- `price_ceiling` - e.g., 300.00
- `search_keywords` - list of optimized search strings for each external source
- `model_hints` - specific model numbers if the user mentioned one

**Prompt strategy:**

```
System: You are a product search specialist. Given a user's shopping
query, extract a structured product specification. Return valid JSON
matching the provided schema. If the user names a specific product,
preserve the exact model name. If the query is vague, infer the most
likely product category and key attributes. Generate 2-3 optimized
search keyword strings suitable for shopping search engines.
```

**Model selection:** Claude claude-sonnet-4-20250514 is used here for low latency and cost efficiency. The task is straightforward extraction and does not require the deeper reasoning of Opus.

**Fallback:** If the Claude API is unavailable, a regex and keyword-based parser handles common query patterns (brand + category + price) to allow degraded but functional search.

### 2.3 Stage 2 - Multi-Source Product Search

**Purpose:** Fan out the structured query to multiple shopping APIs and web sources simultaneously to gather product listings.

**How it works:**

Using the `search_keywords` from Stage 1, the system dispatches parallel async requests to all configured data sources (see Section 5 for the full source list). Each source adapter returns a normalized list of `RawProductListing` objects containing:

- `source_name` - "amazon", "bestbuy", "google_shopping", etc.
- `product_title` - raw title from the source
- `price` - decimal price in USD
- `url` - direct link to the product page
- `availability` - in stock, out of stock, ships in X days
- `seller_rating` - if available
- `image_url` - product thumbnail
- `raw_metadata` - source-specific additional data (JSONB)

**Concurrency model:** All source adapters run as concurrent `asyncio` tasks within a single Celery worker. A per-source timeout of 10 seconds prevents a slow source from blocking the pipeline. Sources that timeout are marked as `partial_failure` in the response and the pipeline continues with whatever data was collected.

**Deduplication:** Before passing results downstream, a deduplication step groups listings that refer to the same product. This uses a combination of:

1. UPC/EAN matching (when available from structured APIs)
2. Normalized model number matching (strip whitespace, case-insensitive)
3. Claude-assisted fuzzy matching for ambiguous cases (e.g., "Sony WH-1000XM5" vs "Sony WH1000XM5 Wireless Headphones Black")

### 2.4 Stage 3 - Data Extraction and Normalization

**Purpose:** Clean, validate, and enrich the raw product data into a unified schema.

**How it works:**

Each `RawProductListing` is processed through a normalization pipeline:

1. **Price normalization** - Convert all prices to USD; strip currency symbols; handle "from $X" ranges by taking the lower bound; detect and flag marketplace vs. first-party pricing.

2. **Product attribute extraction (Claude API)** - For listings that come from web scraping (not structured APIs), Claude extracts structured attributes from the product title and description:
   - Brand
   - Model number
   - Key specifications (storage, size, color, etc.)
   - Condition (new, renewed, open-box)
   - Warranty information

   This uses a structured output schema to guarantee parseable JSON responses. Batch processing: up to 10 listings are sent in a single Claude call to reduce API overhead.

3. **Seller reputation scoring** - Each source/seller is assigned a reputation score (0-100) based on:
   - Known retailer bonuses (Amazon, Best Buy, Walmart, B&H Photo get 85+ base scores)
   - Seller ratings from the source (mapped to 0-100 scale)
   - Historical complaint data (maintained in a static configuration file, updated periodically)

4. **Availability validation** - Flag listings as potentially stale if the source page was cached or if the scrape timestamp is older than 30 minutes.

### 2.5 Stage 4 - Price Comparison and Ranking

**Purpose:** Rank the normalized listings to surface the best deal, guaranteeing at least 3 sources are compared.

**How it works:**

The ranking algorithm computes a composite **Deal Score** for each listing:

```
Deal Score = (0.45 * price_score) +
             (0.25 * seller_score) +
             (0.15 * availability_score) +
             (0.10 * shipping_score) +
             (0.05 * return_policy_score)
```

Where:
- `price_score` = `1.0 - (listing_price / max_price_in_set)` -- lower price scores higher
- `seller_score` = `reputation_score / 100`
- `availability_score` = 1.0 for in-stock, 0.5 for ships-in-3-days, 0.0 for out-of-stock
- `shipping_score` = 1.0 for free shipping, scaled down by shipping cost relative to product price
- `return_policy_score` = 1.0 for 30+ day free returns, 0.5 for 15-29 days, 0.0 for no returns

**Minimum source guarantee:** If fewer than 3 sources returned results, the system triggers a secondary search round with broader keywords (dropping brand or specific attribute constraints). If still under 3, the result is presented with a notice: "Only N sources had this product available."

**Output:** An ordered list of `RankedListing` objects, grouped by unique product, with the best deal flagged.

### 2.6 Stage 5 - Alternative Model Identification (Claude API)

**Purpose:** Recommend alternative or newer models that offer the same or better functionality at a potentially better price point.

**How it works:**

This is the most reasoning-intensive AI stage and uses Claude claude-sonnet-4-20250514 with a carefully designed prompt.

**Input to Claude:**
- The user's original query and intent
- The top-ranked product from Stage 4 (name, specs, price)
- A curated list of other products found during the search that are in the same category but different model numbers

**Prompt strategy:**

```
System: You are a product expert. Given a target product and a list of
related products from the same category, identify which products are
legitimate alternatives or newer models. For each alternative, explain:
1. How it compares on key specifications
2. Whether it is a newer model (successor) or a competing product
3. The value proposition (e.g., "20% cheaper with similar features"
   or "newer model with improved battery life for $30 more")

Only recommend products that are genuinely comparable. Do not recommend
accessories, cases, or unrelated items. Return structured JSON.
```

**Enrichment step:** After Claude identifies alternatives, the system runs a quick targeted search (Stage 2, narrowed) for each alternative model to fetch current pricing from at least 2 sources. This ensures the alternatives come with real, current pricing data rather than Claude's training data (which may be stale).

**Successor model detection:** Claude is specifically prompted to identify newer generation models. For example, if the user searches for "Sony WH-1000XM4," Claude should identify the XM5 as a successor and explain the differences. The system prompt includes instructions to check model number patterns (incremented numbers, year suffixes) and to flag them as `model_relationship: "successor"` vs `model_relationship: "competitor"`.

**Output:** A list of 2-5 `AlternativeProduct` objects, each with:
- `product_name`
- `model_relationship` - "successor", "predecessor", "competitor", "budget_alternative"
- `comparison_summary` - 2-3 sentence plain-English comparison
- `key_differences` - structured list of spec differences
- `price_range` - min/max from live search results
- `recommendation_strength` - "strong", "moderate", "weak"

### 2.7 Stage 6 - Summary Generation (Claude API)

**Purpose:** Produce a human-readable comparison summary that a non-technical user can quickly understand.

**How it works:**

All data from Stages 4 and 5 is passed to Claude with instructions to generate:

1. **Top Pick Summary** (3-4 sentences) - Which product to buy and from where, with the primary reason (e.g., lowest price from a reputable seller with free returns).

2. **Price Comparison Table Data** - Structured JSON for the frontend to render a comparison table. Columns: Source, Price, Shipping, Availability, Seller Rating, Deal Score.

3. **Alternatives Brief** - A short paragraph explaining whether the user should consider alternatives and why (e.g., "The XM5 is available for only $30 more and offers significantly better call quality and battery life.").

4. **Caveats** - Any warnings about pricing (e.g., "The lowest price is from a marketplace seller with limited return options" or "This price may reflect an open-box item").

**Model selection:** Claude claude-sonnet-4-20250514 is used. The summarization task benefits from nuanced language but does not require the longest context windows. Token usage is kept under 2,000 output tokens per summary.

**Tone and style:** The system prompt instructs Claude to write in a helpful, neutral, consumer-advocate tone. No promotional language. Prices are always stated clearly. Trade-offs are presented honestly.

### 2.8 LLM Integration Strategy

**API management:**

| Concern | Approach |
|---------|----------|
| **API Key Security** | Stored in Docker secrets / environment variables; never committed to source control; rotated monthly. |
| **Rate Limiting** | Client-side token bucket limiter set to 80% of the Anthropic tier limit. Celery workers share a Redis-backed counter to coordinate. |
| **Cost Control** | Per-search token budget of 8,000 input + 3,000 output tokens across all stages. Stages 1 and 3 use batch requests to reduce overhead. Monthly budget alerts at 75% and 90% of allocation. |
| **Latency** | Stages 1 and 6 are on the critical path. Claude claude-sonnet-4-20250514 is selected for its speed-to-quality ratio. Streaming responses are used in Stage 6 so the frontend can begin rendering the summary before it is fully generated. |
| **Error Handling** | Exponential backoff with 3 retries on 429/500 errors. If all retries fail, the pipeline degrades gracefully: Stage 1 falls back to keyword parsing; Stage 5 is skipped (no alternatives shown); Stage 6 falls back to a template-based summary. |
| **Model Versioning** | The model identifier is stored in a configuration file, not hardcoded. When Anthropic releases new model versions, the team can update the config and run the evaluation suite before switching. |

**Prompt management:**

All prompts are stored in a dedicated `/prompts` directory as versioned text files. Each prompt has:
- A unique identifier (e.g., `query_understanding_v3`)
- A changelog comment at the top
- Input/output schema definitions as JSON Schema files in the same directory

This allows prompt changes to go through code review and be tracked in version control without modifying application code.

---

## 3. Data Flow

### 3.1 Primary Search Flow

```
User types search query in React frontend
    |
    v
[1] POST /api/v1/search {query: "Sony WH-1000XM5"}
    |
    v
[2] Backend validates request, creates SearchSession record in PostgreSQL
    Returns: {session_id: "uuid", status: "processing"}
    |
    v
[3] Backend dispatches Celery task chain:
    query_understanding -> multi_source_search -> extract_normalize ->
    rank_compare -> identify_alternatives -> generate_summary
    |
    v
[4] Each Celery task publishes progress events to Redis pub/sub:
    Channel: "search:{session_id}"
    Events:
      - {stage: "understanding", status: "complete", detail: "Parsed as headphones search"}
      - {stage: "searching", status: "in_progress", detail: "Querying 5 sources...",
         sources_complete: 2, sources_total: 5}
      - {stage: "searching", status: "complete", detail: "Found 23 listings from 4 sources"}
      - {stage: "comparing", status: "complete", detail: "Best price: $278 at Amazon"}
      - {stage: "alternatives", status: "complete", detail: "Found 3 alternatives"}
      - {stage: "summary", status: "streaming", chunks: ["The best deal...", " is at Amazon..."]}
    |
    v
[5] WebSocket server subscribes to Redis channel "search:{session_id}"
    and forwards all events to the connected client in real-time.
    |
    v
[6] Frontend updates UI progressively:
    - Shows a step indicator (Searching... Comparing... Analyzing...)
    - Populates price comparison table as data arrives
    - Streams summary text as it generates
    |
    v
[7] Final Celery task writes complete results to PostgreSQL:
    - search_sessions table: status = "complete", completed_at = now()
    - search_results table: all ranked listings with deal scores
    - alternative_products table: identified alternatives with comparisons
    - search_summaries table: generated summary text
    |
    v
[8] Final WebSocket event: {stage: "done", status: "complete", result_id: "uuid"}
    Client fetches full results via GET /api/v1/search/{session_id}/results
```

### 3.2 Historical Search Flow

```
User navigates to "My Searches" page
    |
    v
[1] GET /api/v1/history?page=1&limit=20
    |
    v
[2] Backend queries PostgreSQL:
    SELECT ss.*, sr.best_price, sr.best_source
    FROM search_sessions ss
    LEFT JOIN search_results sr ON sr.session_id = ss.id AND sr.rank = 1
    WHERE ss.user_id = :user_id
    ORDER BY ss.created_at DESC
    LIMIT 20 OFFSET 0
    |
    v
[3] Returns paginated list with session_id, query, searched_at,
    best_price, best_source, sources_checked, alternatives_found
    |
    v
[4] User clicks a past search to view full results:
    GET /api/v1/search/{session_id}/results
    Returns the same response shape as a live search.
    |
    v
[5] Optional: User clicks "Re-search" to run the query again
    with fresh pricing data. This triggers the primary search
    flow (Section 3.1) and links the new session to the
    original via a parent_session_id field for price change tracking.
```

### 3.3 Caching Strategy in Data Flow

```
Search request arrives
    |
    v
Check Redis for identical query within last 30 minutes
    |
    +-- Cache HIT --> Return cached session_id, skip to step [8]
    |
    +-- Cache MISS --> Proceed with full pipeline
            |
            v
        For each external source:
            Check Redis for source-specific product cache (TTL: 2 hours)
            |
            +-- Cache HIT for source --> Use cached listings
            |
            +-- Cache MISS for source --> Query external source, cache result
```

### 3.4 Database Schema Overview

**search_sessions**
- id (UUID, PK)
- user_id (UUID, FK, nullable for anonymous users)
- query_text (TEXT)
- parsed_query (JSONB) -- Stage 1 output
- status (ENUM: pending, processing, complete, failed)
- created_at (TIMESTAMPTZ)
- completed_at (TIMESTAMPTZ, nullable)
- parent_session_id (UUID, FK, nullable) -- for re-searches
- total_sources_queried (INT)
- total_listings_found (INT)

**search_results**
- id (UUID, PK)
- session_id (UUID, FK)
- source_name (VARCHAR)
- product_title (TEXT)
- brand (VARCHAR)
- model_number (VARCHAR)
- price (DECIMAL 10,2)
- currency (VARCHAR, default 'USD')
- shipping_cost (DECIMAL 10,2, nullable)
- availability (VARCHAR)
- seller_name (VARCHAR)
- seller_rating (DECIMAL 3,2, nullable)
- product_url (TEXT)
- image_url (TEXT, nullable)
- condition (VARCHAR) -- new, renewed, open-box
- deal_score (DECIMAL 5,4)
- rank (INT)
- raw_metadata (JSONB)
- fetched_at (TIMESTAMPTZ)

**alternative_products**
- id (UUID, PK)
- session_id (UUID, FK)
- target_product_id (UUID, FK -> search_results.id)
- product_name (TEXT)
- model_number (VARCHAR)
- model_relationship (VARCHAR) -- successor, competitor, budget_alternative
- comparison_summary (TEXT)
- key_differences (JSONB)
- price_min (DECIMAL 10,2, nullable)
- price_max (DECIMAL 10,2, nullable)
- recommendation_strength (VARCHAR)
- source_urls (JSONB) -- array of URLs where this alternative was found

**search_summaries**
- id (UUID, PK)
- session_id (UUID, FK, UNIQUE)
- top_pick_summary (TEXT)
- comparison_table_data (JSONB)
- alternatives_brief (TEXT)
- caveats (TEXT, nullable)
- generated_at (TIMESTAMPTZ)
- model_version (VARCHAR) -- Claude model used
- token_usage (JSONB) -- {input: N, output: N} for cost tracking

---

## 4. API Design

### 4.1 REST Endpoints

All endpoints are prefixed with `/api/v1`.

#### Search

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/search` | Initiate a new product search |
| `GET` | `/search/{session_id}` | Get search session status |
| `GET` | `/search/{session_id}/results` | Get complete search results |
| `POST` | `/search/{session_id}/refresh` | Re-run a search with fresh data |

**POST /search**

Request:
```json
{
  "query": "Sony WH-1000XM5 headphones",
  "max_price": 400.00,
  "min_sources": 3,
  "include_alternatives": true
}
```

Response (202 Accepted):
```json
{
  "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "processing",
  "websocket_url": "/ws/search/a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "estimated_duration_seconds": 15
}
```

**GET /search/{session_id}/results**

Response (200 OK):
```json
{
  "session_id": "a1b2c3d4-...",
  "query": "Sony WH-1000XM5 headphones",
  "status": "complete",
  "completed_at": "2026-03-15T10:30:45Z",
  "summary": {
    "top_pick": "The best price for the Sony WH-1000XM5 is $278.00 at Amazon...",
    "alternatives_brief": "Consider the Sony WH-1000XM6 ($329)...",
    "caveats": null
  },
  "comparison": [
    {
      "rank": 1,
      "source": "Amazon",
      "product_title": "Sony WH-1000XM5 Wireless Noise Cancelling Headphones",
      "price": 278.00,
      "shipping": "Free (Prime)",
      "availability": "In Stock",
      "seller_rating": 4.7,
      "condition": "New",
      "deal_score": 0.9245,
      "url": "https://amazon.com/dp/..."
    }
  ],
  "alternatives": [
    {
      "product_name": "Sony WH-1000XM6",
      "model_relationship": "successor",
      "comparison_summary": "The XM6 is the 2026 successor with improved call quality...",
      "key_differences": [
        {"attribute": "Battery Life", "target": "30 hours", "alternative": "40 hours"}
      ],
      "price_range": {"min": 329.00, "max": 349.00},
      "recommendation_strength": "moderate"
    }
  ]
}
```

#### History

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/history` | List past searches (paginated) |
| `GET` | `/history/stats` | Get aggregate stats (total searches, avg savings, etc.) |
| `DELETE` | `/history/{session_id}` | Delete a search from history |
| `DELETE` | `/history` | Clear all search history |

**GET /history** query parameters: `page`, `limit`, `sort`, `q` (full-text search)

#### Health and Meta

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Service health check |
| `GET` | `/sources` | List available data sources and their current status |

### 4.2 WebSocket Events

**Connection:** `ws://{host}/ws/search/{session_id}`

#### Server-to-Client Events

| Event Type | Payload | Description |
|-----------|---------|-------------|
| `connected` | `{session_id}` | Connection acknowledged |
| `stage_update` | `{stage, status, detail}` | Pipeline stage progress |
| `source_result` | `{source_name, listings_found, status}` | Individual source completed |
| `partial_comparison` | `{top_3_listings}` | Early comparison data (sent as soon as 3+ sources are done) |
| `summary_chunk` | `{text, is_final}` | Streamed summary text (from Claude streaming response) |
| `alternative_found` | `{product_name, relationship, price_range}` | Each alternative as identified |
| `complete` | `{session_id, total_time_ms}` | Search pipeline finished |
| `error` | `{code, message, recoverable}` | Error during processing |

**Event sequence for a typical search:**

```
-> connected
-> stage_update {stage: "understanding", status: "complete"}
-> stage_update {stage: "searching", status: "in_progress", sources_complete: 0, sources_total: 5}
-> source_result {source_name: "bestbuy_api", listings_found: 4}
-> source_result {source_name: "amazon_paapi", listings_found: 6}
-> source_result {source_name: "google_shopping", listings_found: 8}
-> partial_comparison {top_3_listings: [...]}
-> source_result {source_name: "walmart", listings_found: 3}
-> source_result {source_name: "bhphoto", listings_found: 2}
-> stage_update {stage: "comparing", status: "complete"}
-> stage_update {stage: "alternatives", status: "in_progress"}
-> alternative_found {product_name: "Sony WH-1000XM6", relationship: "successor"}
-> alternative_found {product_name: "Bose QC Ultra", relationship: "competitor"}
-> stage_update {stage: "alternatives", status: "complete"}
-> summary_chunk {text: "The best deal for the Sony WH-1000XM5 is ", is_final: false}
-> summary_chunk {text: "$278.00 at Amazon...", is_final: false}
-> summary_chunk {text: "", is_final: true}
-> complete {session_id: "...", total_time_ms: 12340}
```

#### Client-to-Server Events

| Event Type | Payload | Description |
|-----------|---------|-------------|
| `cancel` | `{session_id}` | Cancel an in-progress search |
| `ping` | `{}` | Keep-alive (server responds with `pong`) |

### 4.3 Error Responses

All REST error responses follow a consistent format:

```json
{
  "error": {
    "code": "SEARCH_TIMEOUT",
    "message": "The search could not be completed within the time limit.",
    "detail": "3 of 5 sources responded. Partial results are available.",
    "session_id": "a1b2c3d4-...",
    "recoverable": true
  }
}
```

Standard HTTP error codes: 400, 404, 429 (10 searches/min/user), 500, 503.

---

## 5. External Data Sources Strategy

### 5.1 Primary Data Sources (Structured APIs)

| Source | API | Data Provided | Rate Limit | Cost |
|--------|-----|--------------|------------|------|
| **Amazon** | Product Advertising API (PA-API 5.0) | Price, availability, reviews, seller info, product specs | 1 req/sec (scales with revenue) | Free (requires Associates account) |
| **Best Buy** | Best Buy Products API | Price, availability, store inventory, specs, reviews | 5 req/sec | Free (API key required) |
| **Walmart** | Walmart Affiliate API | Price, availability, seller info, reviews | 5 req/sec | Free (affiliate account) |
| **Google Shopping** | SerpApi (Google Shopping endpoint) | Aggregated prices from multiple sellers, price history | Per-plan limits | $50-$250/mo depending on volume |
| **eBay** | Browse API | Price, condition (new/used), seller ratings, auction data | 5000 calls/day | Free (developer account) |

### 5.2 Secondary Data Sources (Scraping with Structured Parsing)

| Source | Method | Data Provided | Notes |
|--------|--------|--------------|-------|
| **B&H Photo** | HTTP + BeautifulSoup | Price, availability, specs | Excellent for electronics; relatively stable HTML structure |
| **Newegg** | HTTP + BeautifulSoup | Price, availability, reviews | Good for PC components and electronics |
| **Target** | HTTP + Playwright | Price, availability, store pickup | Requires JS rendering; uses Playwright headless browser |
| **Costco** | HTTP + Playwright | Member price, availability | Requires JS rendering; prices may be member-only |

### 5.3 Supplementary Data Sources

| Source | Purpose |
|--------|---------|
| **CamelCamelCamel** (scraping) | Amazon price history to determine if current price is a good deal |
| **RTings.com** (scraping) | Expert product reviews and comparison data for electronics |
| **Google Knowledge Graph API** | Product specifications, release dates, successor models |

### 5.4 Source Adapter Architecture

Each external source is implemented as a Python class inheriting from `BaseSourceAdapter`:

```
BaseSourceAdapter (abstract)
  - search(keywords: list[str], filters: dict) -> list[RawProductListing]
  - get_product_detail(product_id: str) -> ProductDetail
  - health_check() -> SourceHealth

Implementations:
  - AmazonPAAPIAdapter
  - BestBuyAPIAdapter
  - WalmartAPIAdapter
  - GoogleShoppingAdapter (via SerpApi)
  - EbayBrowseAdapter
  - BHPhotoScraperAdapter
  - NeweggScraperAdapter
  - TargetPlaywrightAdapter
  - CostcoPlaywrightAdapter
```

Each adapter handles its own authentication, rate limiting, retry logic, response parsing, and error reporting.

### 5.5 Rate Limiting Strategy

**Per-source rate limiting:** Each source adapter maintains a Redis-backed token bucket that enforces the source's published rate limits. All Celery workers share the same Redis counters to prevent aggregate over-usage.

**Global search rate limiting:** Users are limited to 10 searches per minute and 200 searches per day. Enforced at both the Nginx layer and FastAPI backend via Redis counters.

**Backpressure:** If a source returns HTTP 429, the adapter pauses requests for the duration in the `Retry-After` header (or 60 seconds default), marks the source as `throttled` in Redis, and other concurrent searches skip it temporarily.

### 5.6 Caching Strategy

| Cache Layer | Key Pattern | TTL | Purpose |
|------------|-------------|-----|---------|
| **Search result cache** | `search:{sha256(normalized_query)}` | 30 minutes | Avoid re-running identical searches |
| **Product listing cache** | `product:{source}:{product_id}` | 2 hours | Avoid re-fetching same product from same source |
| **Source health cache** | `health:{source}` | 5 minutes | Track which sources are currently responsive |
| **Claude response cache** | `llm:{sha256(prompt)}` | 24 hours | Cache identical LLM calls |
| **Alternative model cache** | `alt:{model_number}` | 7 days | Alternative model relationships change infrequently |

All caches use TTL-based expiration. No manual invalidation is needed for MVP.

---

## 6. Service Architecture (Docker Compose)

### 6.1 Service Definitions

```
docker-compose.yml
|
+-- nginx          (reverse proxy, static files)
+-- frontend       (React build served by nginx)
+-- backend        (FastAPI application server)
+-- worker         (Celery workers for AI/search pipeline)
+-- beat           (Celery Beat for scheduled tasks)
+-- postgres       (PostgreSQL database)
+-- redis          (Cache, message broker, pub/sub)
+-- playwright     (Playwright browser service for JS-heavy scraping)
```

### 6.2 Service Details

**nginx (Reverse Proxy)**
- Image: `nginx:1.27-alpine`
- Ports: `80:80`, `443:443`
- Handles SSL termination, route `/` to React, `/api/*` to FastAPI, `/ws/*` to WebSocket handler, gzip compression, static asset caching
- Depends on: frontend, backend

**frontend (React SPA)**
- Multi-stage build: `node:20-alpine` for build, `nginx:1.27-alpine` for serving
- Ports: `3000:80` (internal)
- Environment: `VITE_API_BASE_URL=/api/v1`, `VITE_WS_BASE_URL=/ws`

**backend (FastAPI API Server)**
- Base image: `python:3.12-slim`
- Ports: `8000:8000` (internal)
- Command: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4`
- Environment: DATABASE_URL, REDIS_URL, ANTHROPIC_API_KEY, CELERY_BROKER_URL, CELERY_RESULT_BACKEND
- Depends on: postgres, redis
- Resource limits: 1 CPU, 1GB RAM

**worker (Celery AI/Search Workers)**
- Same Dockerfile as backend
- Command: `celery -A app.celery_app worker --loglevel=info --concurrency=4 --pool=gevent`
- Additional environment: all shopping API keys, PLAYWRIGHT_WS_ENDPOINT
- Depends on: postgres, redis, playwright
- Scaling: `docker compose up --scale worker=3` for horizontal scaling
- Pool: `gevent` chosen because workload is I/O-bound (HTTP requests, API calls)
- Resource limits: 2 CPU, 2GB RAM per instance

**beat (Celery Beat Scheduler)**
- Same Dockerfile as backend
- Scheduled tasks: source health checks (5 min), cache pruning (1 hour), usage stats (24 hours), alternative model cache refresh (24 hours)
- Resource limits: 0.25 CPU, 256MB RAM

**postgres (Database)**
- Image: `postgres:16-alpine`
- Ports: `5432:5432` (internal only)
- Volumes: `postgres_data:/var/lib/postgresql/data`, init.sql for schema
- Tuning: shared_buffers=256MB, effective_cache_size=512MB, work_mem=16MB
- Resource limits: 1 CPU, 1GB RAM

**redis (Cache and Message Broker)**
- Image: `redis:7-alpine`
- Ports: `6379:6379` (internal only)
- Command: `redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru`
- Database allocation: DB 0 (app cache), DB 1 (Celery broker), DB 2 (Celery results), DB 3 (rate limiters), DB 4 (WebSocket pub/sub)
- Resource limits: 0.5 CPU, 768MB RAM

**playwright (Browser Service)**
- Image: `mcr.microsoft.com/playwright:v1.50.0-noble`
- Command: `npx playwright launch-server --browser chromium --port 3000`
- Ports: `3000:3000` (internal only; workers connect via WebSocket)
- Purpose: Headless Chromium for scraping JS-heavy sites
- Resource limits: 2 CPU, 2GB RAM

### 6.3 Network and Volumes

All services on a single internal Docker bridge network `shopping_net`. Only nginx exposes ports to the host. Named volumes: `postgres_data`, `redis_data`.

### 6.4 Environment File Structure

```
.env                    # Shared defaults (non-secret)
.env.local              # Local development overrides (gitignored)
.env.production         # Production values (gitignored, managed via secrets)
```

Required secrets (never committed): ANTHROPIC_API_KEY, DB_PASSWORD, AMAZON_PAAPI_ACCESS_KEY, AMAZON_PAAPI_SECRET_KEY, BESTBUY_API_KEY, WALMART_API_KEY, SERPAPI_KEY, EBAY_APP_ID.

---

## 7. Security and Compliance

### 7.1 API Security

- **Authentication:** Session-based for registered users; anonymous usage with stricter rate limits (3 searches/hour vs. 200/day for registered).
- **Input validation:** Pydantic models sanitize all input. Search queries limited to 500 characters, stripped of HTML/script tags.
- **CORS:** Only frontend origin allowed.
- **HTTPS:** Enforced in production via nginx SSL termination.

### 7.2 Data Privacy

- Minimal PII collected. Email for registered users only.
- User IP addresses never forwarded to external shopping APIs.
- User queries sent to Claude API are not used for model training per Anthropic's API data policy. No PII included in prompts.
- Users can delete their entire search history via the API.

### 7.3 Affiliate Disclosure

If affiliate links are used, the frontend displays: "Some links may be affiliate links. This does not affect the prices shown or our recommendations."

---

## 8. Scalability and Performance

### 8.1 Performance Targets

| Metric | Target | Strategy |
|--------|--------|----------|
| Search initiation response | < 200ms | Return session ID immediately; process async |
| Full search completion | < 20 seconds | Parallel source queries; 10s per-source timeout |
| Partial results available | < 8 seconds | Stream results as sources complete |
| Historical search page load | < 300ms | Indexed database queries; pagination |
| Concurrent searches | 50 simultaneous | Scale Celery workers horizontally |
| WebSocket connections | 500 concurrent | FastAPI async handlers; Redis pub/sub |

### 8.2 Horizontal Scaling

- **Workers:** `docker compose up --scale worker=N` -- Redis broker distributes tasks automatically.
- **Backend:** Multiple uvicorn instances behind nginx. Stateless design (session state in Redis).
- **Database:** Single PostgreSQL for MVP. Future: read replicas, PgBouncer connection pooling.

### 8.3 Cost Optimization

- **Claude API:** Estimated $0.02-$0.05 per search (~4,000 input + ~2,000 output tokens across all stages).
- **SerpApi:** $50/month for 5,000 searches. Falls back to direct scraping if quota exceeded.
- **Infrastructure:** A single 4-core VM with 16GB RAM handles ~50 concurrent users. Estimated $40-$80/month.

---

## 9. Monitoring and Observability

### 9.1 Application Metrics

Collected via Prometheus client library, exposed at `/metrics`:

- **Search:** searches_initiated, searches_completed, searches_failed, search_duration_seconds (histogram)
- **Sources:** source_requests_total, source_errors_total, source_latency_seconds (all by source)
- **AI:** llm_requests_total, llm_tokens_used (by stage), llm_latency_seconds, llm_errors_total
- **Cache:** cache_hits_total, cache_misses_total (by layer)
- **WebSocket:** ws_connections_active, ws_messages_sent_total

### 9.2 Logging

- Structured JSON logs via `structlog`
- DEBUG in development, INFO in production
- Every log entry includes `session_id` for end-to-end tracing
- stdout captured by Docker, forwarded to log aggregation (Grafana Loki or Datadog)

### 9.3 Alerting

| Alert | Condition | Severity |
|-------|-----------|----------|
| Search failure rate | > 10% in 5 minutes | High |
| Source unavailable | Any source failing > 15 minutes | Medium |
| Claude API errors | > 5 errors in 1 minute | High |
| Search latency | p95 > 30 seconds | Medium |
| Redis memory | > 80% of maxmemory | Medium |
| PostgreSQL connections | > 80% of max_connections | Medium |
| Worker queue depth | > 100 pending tasks | High |

---

## Appendix A: Project Directory Structure

```
ShoppingCompanion/
  docker-compose.yml
  docker-compose.override.yml
  .env.example
  ARCHITECTURE.md

  nginx/
    nginx.conf
    ssl/

  frontend/
    Dockerfile
    package.json
    src/
      components/   (SearchBar, SearchProgress, ComparisonTable,
                     AlternativesList, HistoryList, SummaryCard)
      hooks/        (useSearch, useHistory)
      services/     (api.ts, websocket.ts)
      store/        (searchStore.ts)
      pages/        (SearchPage, HistoryPage, ResultsPage)

  backend/
    Dockerfile
    requirements.txt
    app/
      main.py, celery_app.py, config.py
      api/          (router, search, history, health, websocket)
      models/       (database.py, schemas.py)
      services/     (search_orchestrator, query_understanding, source_manager,
                     data_normalizer, price_ranker, alternative_finder,
                     summary_generator)
      sources/      (base, amazon, bestbuy, walmart, google_shopping,
                     ebay, bhphoto, newegg, target, costco)
      llm/          (client, rate_limiter, cache)
      prompts/      (versioned prompt files + JSON schemas)
      tasks/        (search_tasks, maintenance_tasks)
      db/           (session.py, migrations/)

  tests/
    backend/        (API tests, pipeline tests, adapter tests, LLM tests)
    frontend/       (component tests)
```

---

## Appendix B: Future Enhancements

1. **Price alerts** - Periodic re-checks with email/push notifications on price drops.
2. **Price history charts** - Historical trends from cached data and CamelCamelCamel.
3. **User accounts and wishlists** - Persistent profiles with saved products.
4. **Browser extension** - Show comparisons when visiting product pages on retailer sites.
5. **Mobile app** - React Native sharing the same backend API.
6. **Multi-currency support** - Locale detection and exchange rate conversion.
7. **Review aggregation** - Sentiment analysis across sources using Claude.
8. **Coupon integration** - Surface applicable discount codes from coupon APIs.
