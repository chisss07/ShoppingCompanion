# Shopping Companion — Database Architecture Design

**Version:** 1.0
**Date:** 2026-03-15
**Status:** Draft
**Scope:** PostgreSQL schema design, query patterns, performance optimization, data lifecycle, and Redis caching strategy for the AI-powered Shopping Companion application.

---

## Table of Contents

1. [Overview](#overview)
2. [Database Schema Design](#database-schema-design)
   - [Entity-Relationship Diagram](#entity-relationship-diagram)
   - [Table Definitions](#table-definitions)
3. [Query Patterns](#query-patterns)
4. [Performance Optimization](#performance-optimization)
5. [Data Lifecycle](#data-lifecycle)
6. [Redis Caching Strategy](#redis-caching-strategy)
7. [Operational Checklist](#operational-checklist)

---

## Overview

The Shopping Companion database is built on **PostgreSQL 16** as the primary relational store and **Redis 7** as the caching and session layer. The design prioritizes:

- Sub-100ms response times for cached queries and sub-500ms for uncached queries
- Accurate, timestamped price history across multiple retail sources
- Full-text search over product names and descriptions
- AI-generated comparison content stored alongside structured data
- Horizontal scalability through table partitioning and read replicas

**Target SLAs:**

| Metric | Target |
|---|---|
| Availability | 99.9% |
| RTO | < 30 minutes |
| RPO | < 5 minutes |
| p95 query latency (cached) | < 50 ms |
| p95 query latency (uncached) | < 400 ms |

---

## Database Schema Design

### Entity-Relationship Diagram

```
+------------------+          +----------------------+          +------------------+
|     sources      |          |    price_entries     |          |     products     |
|------------------|          |----------------------|          |------------------|
| PK source_id     |<----+    | PK price_entry_id    |    +---->| PK product_id    |
|    name          |     |    |    product_id (FK) --+----+    |    name          |
|    base_url      |     |    |    source_id  (FK) --+----+    |    brand         |
|    logo_url      |     +----+--  source_id         |         |    model_number  |
|    reliability_  |          |    price             |         |    category      |
|      score       |          |    currency          |         |    description   |
|    is_active     |          |    availability      |         |    image_url     |
|    created_at    |          |    product_url       |         |    created_at    |
|    updated_at    |          |    captured_at       |         |    updated_at    |
+------------------+          |    is_active         |         +--------+---------+
                              |    partition key:    |                  |
                              |      captured_at     |                  |
                              +----------+-----------+                  |
                                         |                              |
                              +----------+-----------+        +---------+----------+
                              | comparison_summaries |        | product_alternatives|
                              |----------------------|        |--------------------|
                              | PK summary_id        |        | PK alternative_id  |
                              |    product_id  (FK)--+--+     |    product_id (FK)-+
                              |    generated_by_model|  |     |    alt_product_id--+
                              |    summary_text      |  +---->|      (FK)          |
                              |    recommendation    |        |    relationship_   |
                              |    highlights (jsonb)|        |      type          |
                              |    created_at        |        |    similarity_     |
                              |    expires_at        |        |      score         |
                              +----------------------+        |    note            |
                                                             |    created_at      |
                                                             +--------------------+

+------------------+          +----------------------+
|    searches      |          |   search_results     |
|------------------|          |----------------------|
| PK search_id     |<----+    | PK result_id         |
|    user_id       |     |    |    search_id   (FK)--+----+
|    session_id    |     +----+--  search_id          |
|    query_text    |          |    product_id  (FK) --+---------> products
|    filters (jsnb)|          |    rank_position      |
|    status        |          |    relevance_score    |
|    result_count  |          |    lowest_price       |
|    created_at    |          |    created_at         |
|    completed_at  |          +----------------------+
+------------------+
```

**Relationship Summary:**

- One `search` produces many `search_results`
- One `search_result` links to one `product`
- One `product` has many `price_entries` (one per source, captured over time)
- One `source` provides many `price_entries`
- One `product` has many `product_alternatives` (self-referencing through junction table)
- One `product` may have one or more `comparison_summaries` (AI-generated, time-bounded)

---

### Table Definitions

#### `sources`

Stores canonical information about each shopping source or retailer. This table is small, mostly static, and referenced by every price entry.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `source_id` | `UUID` | PK, DEFAULT gen_random_uuid() | Unique identifier for the source |
| `name` | `VARCHAR(120)` | NOT NULL, UNIQUE | Human-readable retailer name (e.g., "Amazon", "Best Buy") |
| `base_url` | `VARCHAR(500)` | NOT NULL | Root domain URL for constructing links |
| `logo_url` | `VARCHAR(500)` | | URL to the retailer's logo asset |
| `reliability_score` | `NUMERIC(3,2)` | CHECK (0.00 to 1.00) | Rolling score reflecting data freshness and accuracy |
| `scrape_frequency_minutes` | `INTEGER` | NOT NULL, DEFAULT 60 | How often this source should be re-scraped |
| `is_active` | `BOOLEAN` | NOT NULL, DEFAULT TRUE | Soft-disable a source without deleting price history |
| `metadata` | `JSONB` | | Flexible field for source-specific config (auth headers, rate limits) |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT NOW() | Record creation time |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT NOW() | Last modification time, maintained by trigger |

`metadata` JSONB allows storing source-specific scraping configuration without schema changes. `reliability_score` is updated by a background job that measures how often scraped prices match verified prices.

---

#### `products`

The canonical product catalog. Each unique physical product model has exactly one row. Products are normalized to avoid duplication across searches and sources.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `product_id` | `UUID` | PK, DEFAULT gen_random_uuid() | Unique product identifier |
| `name` | `VARCHAR(500)` | NOT NULL | Full product name |
| `brand` | `VARCHAR(200)` | NOT NULL | Manufacturer or brand name |
| `model_number` | `VARCHAR(200)` | | Manufacturer model number or SKU |
| `category` | `VARCHAR(200)` | NOT NULL | Top-level product category (e.g., "Laptops", "Headphones") |
| `subcategory` | `VARCHAR(200)` | | More specific classification |
| `description` | `TEXT` | | Full product description |
| `description_tsv` | `TSVECTOR` | | Generated column for full-text search, derived from name + brand + description |
| `image_url` | `VARCHAR(500)` | | Primary product image URL |
| `specifications` | `JSONB` | | Flexible key-value store for product specs (RAM, weight, color, etc.) |
| `release_year` | `SMALLINT` | | Model year for consumer electronics |
| `is_discontinued` | `BOOLEAN` | NOT NULL, DEFAULT FALSE | Whether this model is no longer manufactured |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT NOW() | First time this product was seen |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT NOW() | Last metadata update |

`description_tsv` is maintained by a trigger that calls `to_tsvector('english', ...)` on inserts and updates to `name`, `brand`, and `description`. This avoids recomputing the vector at query time. Deduplication logic in the application layer must resolve conflicts before inserting — matching on `brand` + `model_number` when available, falling back to fuzzy name matching.

---

#### `price_entries`

Records a price observed for a specific product at a specific source at a specific point in time. This is the highest-volume table in the system and is range-partitioned by `captured_at`.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `price_entry_id` | `UUID` | PK, DEFAULT gen_random_uuid() | Unique price observation identifier |
| `product_id` | `UUID` | NOT NULL, FK -> products | The product this price is for |
| `source_id` | `UUID` | NOT NULL, FK -> sources | The source this price was observed at |
| `price` | `NUMERIC(12,2)` | NOT NULL | Observed price in the recorded currency |
| `currency` | `CHAR(3)` | NOT NULL, DEFAULT 'USD' | ISO 4217 currency code |
| `original_price` | `NUMERIC(12,2)` | | Pre-discount or MSRP price, if shown |
| `discount_percent` | `NUMERIC(5,2)` | | Calculated discount percentage |
| `availability` | `VARCHAR(50)` | NOT NULL | One of: 'in_stock', 'out_of_stock', 'limited', 'preorder', 'unknown' |
| `product_url` | `VARCHAR(1000)` | NOT NULL | Direct link to the product listing at the source |
| `shipping_cost` | `NUMERIC(8,2)` | | Shipping cost if determinable (NULL = unknown) |
| `captured_at` | `TIMESTAMPTZ` | NOT NULL | When this price was observed — used as partition key |
| `is_active` | `BOOLEAN` | NOT NULL, DEFAULT TRUE | FALSE once a newer entry for the same product+source exists |

`is_active` is set to FALSE on older rows by a background job when a new price is captured for the same `(product_id, source_id)` pair. This allows efficient "current price" queries without a MAX(captured_at) subquery across the full partitioned table.

---

#### `searches`

Records every search query issued by a user or session.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `search_id` | `UUID` | PK, DEFAULT gen_random_uuid() | Unique search identifier |
| `user_id` | `UUID` | | Application-level user identifier (NULL for anonymous) |
| `session_id` | `UUID` | NOT NULL | Session identifier for grouping anonymous activity |
| `query_text` | `VARCHAR(1000)` | NOT NULL | The raw text the user searched for |
| `query_tsv` | `TSVECTOR` | | Full-text vector of the query, for similarity matching |
| `filters` | `JSONB` | | Structured filters applied (price range, category, brand, etc.) |
| `status` | `VARCHAR(20)` | NOT NULL, DEFAULT 'pending' | One of: 'pending', 'processing', 'completed', 'failed' |
| `result_count` | `INTEGER` | | Number of results returned |
| `ai_intent` | `VARCHAR(100)` | | AI-classified search intent (e.g., 'price_comparison', 'find_alternative') |
| `source_hint` | `VARCHAR(50)` | | Client that initiated the search ('mobile', 'web', 'api') |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT NOW() | When the search was issued |
| `completed_at` | `TIMESTAMPTZ` | | When the search finished processing |

`user_id` is nullable to support unauthenticated searches. `ai_intent` is populated by the AI layer after query parsing and informs which downstream pipelines activate.

---

#### `search_results`

Junction table linking a search to the products it returned, with ranking and relevance metadata.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `result_id` | `UUID` | PK, DEFAULT gen_random_uuid() | Unique result identifier |
| `search_id` | `UUID` | NOT NULL, FK -> searches | The search this result belongs to |
| `product_id` | `UUID` | NOT NULL, FK -> products | The product returned |
| `rank_position` | `SMALLINT` | NOT NULL | Display rank (1 = top result) |
| `relevance_score` | `NUMERIC(5,4)` | | Relevance score from the AI ranking model (0.0000-1.0000) |
| `lowest_price` | `NUMERIC(12,2)` | | Snapshot of the lowest observed price at search time |
| `lowest_price_source_id` | `UUID` | FK -> sources | Source where the lowest price was observed |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT NOW() | When this result was recorded |

`lowest_price` and `lowest_price_source_id` are denormalized snapshots captured at search time. They preserve the price context of the search without requiring a join back to `price_entries` for historical result display.

---

#### `product_alternatives`

A self-referencing junction table capturing relationships between products: newer models, competitors, budget alternatives, premium upgrades, and accessories.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `alternative_id` | `UUID` | PK, DEFAULT gen_random_uuid() | Unique relationship identifier |
| `product_id` | `UUID` | NOT NULL, FK -> products | The base product |
| `alt_product_id` | `UUID` | NOT NULL, FK -> products | The alternative product |
| `relationship_type` | `VARCHAR(50)` | NOT NULL | One of: 'newer_model', 'older_model', 'competitor', 'budget_alternative', 'premium_upgrade', 'accessory' |
| `similarity_score` | `NUMERIC(4,3)` | | AI-generated similarity score (0.000-1.000) |
| `note` | `VARCHAR(500)` | | Human or AI-generated note explaining the relationship |
| `is_verified` | `BOOLEAN` | NOT NULL, DEFAULT FALSE | Whether this relationship has been human-verified |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT NOW() | When this relationship was recorded |
| `updated_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT NOW() | Last update |

Relationships are directional. A CHECK constraint prevents a product from being its own alternative: `CHECK (product_id <> alt_product_id)`. Reverse relationships (e.g., both 'newer_model' and 'older_model' directions) may coexist as separate rows and are useful for bi-directional UI queries.

---

#### `comparison_summaries`

Stores AI-generated comparison text for a product across its observed sources. This content is expensive to generate and is cached both here and in Redis.

| Column | Type | Constraints | Description |
|---|---|---|---|
| `summary_id` | `UUID` | PK, DEFAULT gen_random_uuid() | Unique summary identifier |
| `product_id` | `UUID` | NOT NULL, FK -> products | The product being compared |
| `generated_by_model` | `VARCHAR(100)` | NOT NULL | The AI model version that produced this summary |
| `summary_text` | `TEXT` | NOT NULL | Full AI-generated comparison narrative |
| `recommendation` | `VARCHAR(20)` | | One of: 'best_value', 'best_quality', 'best_availability', 'mixed' |
| `highlights` | `JSONB` | | Structured pros/cons and key comparison points per source |
| `source_ids_included` | `UUID[]` | NOT NULL | Array of source IDs whose data was used to generate this summary |
| `price_snapshot` | `JSONB` | | Prices per source at time of generation, for display without a live join |
| `created_at` | `TIMESTAMPTZ` | NOT NULL, DEFAULT NOW() | When this summary was generated |
| `expires_at` | `TIMESTAMPTZ` | NOT NULL | When this summary should be considered stale (DEFAULT: created_at + 4 hours) |

`expires_at` governs freshness. The application always checks this before serving. If expired, a new summary is generated asynchronously while the expired one is served as a fallback with a "prices may have changed" notice. `source_ids_included` allows validating whether a stored summary covers all currently active sources.

---

## Query Patterns

### Pattern 1 — Recent searches with latest prices

Retrieves the last N searches for a user or session, with the current lowest price for each returned product.

**Access pattern:** Search history screen. Latency budget: 200ms uncached.
**Tables touched:** `searches`, `search_results`, `price_entries`, `sources`

Key predicates: filter by `user_id` or `session_id`; order by `searches.created_at DESC`; for each product retrieve the single `price_entries` row where `is_active = TRUE` with the lowest price.

**Supporting indexes:**
- `idx_searches_user_id_created_at` on `searches(user_id, created_at DESC)`
- `idx_searches_session_id_created_at` on `searches(session_id, created_at DESC)`
- `idx_price_entries_product_active` on `price_entries(product_id, is_active)` WHERE `is_active = TRUE` — partial index dramatically reduces the working set

---

### Pattern 2 — Comparison data for a product across sources

Retrieves the current price, availability, and URL for a specific product at every active source, plus the latest AI comparison summary.

**Access pattern:** Product detail and comparison screen. Latency budget: 150ms uncached.
**Tables touched:** `price_entries`, `sources`, `comparison_summaries`

Key predicates: `price_entries` by `product_id` and `is_active = TRUE`; `sources` by `is_active = TRUE`; `comparison_summaries` by `product_id` and `expires_at > NOW()`.

**Supporting indexes:**
- `idx_price_entries_product_active` (partial, as above)
- `idx_comparison_summaries_product_expires` on `comparison_summaries(product_id, expires_at DESC)`

---

### Pattern 3 — Price history for a product over time

Retrieves all price observations for a product at a specific source (or all sources) over a date range, for rendering price history charts.

**Access pattern:** Price history chart component. Date ranges are typically 30, 90, or 365 days. Latency budget: 300ms uncached.
**Tables touched:** `price_entries` (one or more partitions)

Key predicates: `product_id`, optional `source_id`, `captured_at` between start and end date.

**Supporting indexes:**
- `idx_price_entries_product_source_captured` on `price_entries(product_id, source_id, captured_at DESC)` — local to each partition; partition pruning eliminates irrelevant month partitions automatically

For the 365-day range query, the `mv_monthly_price_stats` materialized view provides pre-aggregated monthly min/max/avg per `(product_id, source_id)`.

---

### Pattern 4 — Find alternative models for a product

Retrieves all products related to a given product, filtered by relationship type, ordered by similarity score.

**Access pattern:** "You might also consider" section. Latency budget: 100ms uncached.
**Tables touched:** `product_alternatives`, `products`, `price_entries`

**Supporting indexes:**
- `idx_product_alternatives_product_type_score` on `product_alternatives(product_id, relationship_type, similarity_score DESC)`

---

### Pattern 5 — Full-text search on product names and descriptions

Retrieves products whose name, brand, or description matches a user-supplied query string, ranked by text relevance.

**Access pattern:** Every search query that does not hit the Redis search cache. Latency budget: 300ms uncached.
**Tables touched:** `products`

Match predicate: `description_tsv @@ plainto_tsquery('english', :query)`. Ordered by `ts_rank(description_tsv, query) DESC`.

**Supporting indexes:**
- `idx_products_description_tsv` — GIN index on `products(description_tsv)` — GIN is optimal for static tsvector columns and supports all tsquery operators

---

## Performance Optimization

### Indexing Strategy

| Index Name | Table | Columns | Type | Where Clause | Serves |
|---|---|---|---|---|---|
| `idx_searches_user_id_created_at` | `searches` | `(user_id, created_at DESC)` | B-tree | — | Pattern 1 |
| `idx_searches_session_id_created_at` | `searches` | `(session_id, created_at DESC)` | B-tree | — | Pattern 1 |
| `idx_search_results_search_id` | `search_results` | `(search_id)` | B-tree | — | Pattern 1 |
| `idx_search_results_product_id` | `search_results` | `(product_id)` | B-tree | — | General |
| `idx_products_brand_category` | `products` | `(brand, category)` | B-tree | — | Browsing |
| `idx_products_description_tsv` | `products` | `(description_tsv)` | GIN | — | Pattern 5 |
| `idx_products_specifications` | `products` | `(specifications)` | GIN | — | Spec filtering |
| `idx_price_entries_product_active` | `price_entries` | `(product_id, is_active)` | B-tree | WHERE `is_active = TRUE` | Patterns 1, 2 |
| `idx_price_entries_product_source_captured` | `price_entries` | `(product_id, source_id, captured_at DESC)` | B-tree | — | Pattern 3 |
| `idx_price_entries_source_captured` | `price_entries` | `(source_id, captured_at DESC)` | B-tree | — | Source analytics |
| `idx_product_alternatives_product_type_score` | `product_alternatives` | `(product_id, relationship_type, similarity_score DESC)` | B-tree | — | Pattern 4 |
| `idx_product_alternatives_alt_product_id` | `product_alternatives` | `(alt_product_id)` | B-tree | — | Reverse lookups |
| `idx_comparison_summaries_product_expires` | `comparison_summaries` | `(product_id, expires_at DESC)` | B-tree | — | Pattern 2 |
| `idx_sources_active` | `sources` | `(is_active, name)` | B-tree | WHERE `is_active = TRUE` | All source joins |
| `idx_searches_filters` | `searches` | `(filters)` | GIN | — | Analytics queries |

**Index maintenance notes:**
- GIN indexes on JSONB (`specifications`, `filters`) are larger and slower to update than B-tree indexes. Monitor write amplification on the `products` and `searches` tables.
- All indexes on `price_entries` are created on each partition individually. PostgreSQL 16 propagates index definitions from the parent table to new partitions automatically.
- Unused indexes are identified monthly via `pg_stat_user_indexes` (rows with `idx_scan = 0` after 30+ days). Unused indexes are dropped to reduce write overhead.

---

### Partitioning Strategy for `price_entries`

**Partition type:** RANGE on `captured_at`
**Partition interval:** Monthly
**Partition naming:** `price_entries_YYYY_MM`

**Partition lifecycle:**

| Age | State | Action |
|---|---|---|
| Current month | Hot | Actively written and read |
| 1-3 months old | Warm | Read-heavy, still on primary storage |
| 4-12 months old | Cool | Reads only; tablespace migration to slower storage |
| 13-24 months old | Cold | Minimal reads; migrated to archival tablespace |
| > 24 months | Archive | Detached, exported to object storage as Parquet, dropped |

A scheduled job creates the next month's partition on the 25th of each month. A separate job on the 1st evaluates partitions for tablespace migration and archival export. Partitions are only dropped after an export is confirmed.

**Partition pruning:** Automatic when `captured_at` conditions are provided as literals or bind parameters. Any query touching `price_entries` without a `captured_at` predicate will scan all partitions — this must be caught in query review.

---

### Connection Pooling Configuration

**Pooler:** PgBouncer 1.22 in transaction mode

Transaction mode is selected because the application uses short, discrete transactions with no session-level state (no `SET`, no advisory locks, no temporary tables in application code).

| Parameter | Value | Rationale |
|---|---|---|
| `pool_mode` | `transaction` | Minimizes server connections |
| `max_client_conn` | `500` | Max simultaneous application connections to PgBouncer |
| `default_pool_size` | `25` | Server connections per database/user pair |
| `min_pool_size` | `5` | Keep minimum connections warm |
| `reserve_pool_size` | `10` | Burst capacity for traffic spikes |
| `reserve_pool_timeout` | `3s` | Seconds before using reserve pool |
| `server_idle_timeout` | `600s` | Idle server connection max age before close |
| `server_lifetime` | `3600s` | Max age of any server connection (prevents bloat) |
| `query_wait_timeout` | `15s` | Seconds a client waits before receiving an error |
| `max_db_connections` | `60` | Absolute ceiling on PostgreSQL server connections |

Write traffic routes to the primary; read traffic routes to read replicas via a separate PgBouncer pool. The application uses two distinct connection strings: `DB_WRITE_URL` and `DB_READ_URL`.

---

### Materialized Views

**`mv_current_prices`**

Provides the current active price for every `(product_id, source_id)` pair in a single flat row. Refreshed every 5 minutes via CONCURRENT refresh (avoids locking reads). Indexed on `(product_id)` and `(product_id, price ASC)`.

Columns: `product_id`, `source_id`, `source_name` (denormalized), `price`, `currency`, `availability`, `product_url`, `last_captured_at`.

---

**`mv_monthly_price_stats`**

Pre-aggregated monthly price statistics per `(product_id, source_id)`. Powers price history charts for date ranges exceeding 90 days. Refreshed nightly at 02:00 UTC via CONCURRENT refresh. Indexed on `(product_id, source_id, year_month DESC)`.

Columns: `product_id`, `source_id`, `year_month` (truncated to first of month), `min_price`, `max_price`, `avg_price`, `observation_count`.

---

**`mv_popular_products`**

Products ranked by search frequency and price view count over the trailing 7 days. Refreshed every 30 minutes. Used by the Redis cache warming job.

Columns: `product_id`, `product_name`, `search_count_7d`, `view_count_7d`, `avg_lowest_price`, `rank`.

---

## Data Lifecycle

### Price Data Retention Policy

| Tier | Age Range | Granularity | Storage | Action |
|---|---|---|---|---|
| Hot | 0-90 days | Every observation | Primary NVMe | No action; fully queryable |
| Warm | 91-180 days | Every observation | Primary NVMe | Read-only partition |
| Cool | 181-365 days | Daily min/max/avg | Standard SSD tablespace | Raw rows replaced by daily aggregates |
| Cold | 1-2 years | Monthly min/max/avg | Archival tablespace | Daily aggregates replaced by monthly aggregates |
| Archive | > 2 years | Monthly aggregates exported to Parquet | Object storage (S3/GCS) | Partition detached and dropped after export validation |

Before compacting raw rows to aggregates, the system validates that aggregates have been computed and checkpointed. Raw rows are only deleted after preservation is confirmed.

---

### Search History Cleanup

| User Type | Retention Period | Deletion Method |
|---|---|---|
| Authenticated users | 12 months | Soft delete (is_deleted flag), hard delete after 90-day grace period |
| Anonymous sessions | 30 days | Hard delete |
| Searches with no results | 7 days | Hard delete |

GDPR right-to-erasure requests trigger immediate soft deletion of all `searches` and `search_results` rows for the affected `user_id`. Hard deletion completes within 30 days. Associated `products` and `price_entries` data is not user-specific and is not deleted.

The cleanup job runs nightly at 03:00 UTC, deleting in batches of 10,000 rows to avoid long-running transactions and autovacuum interference. `ANALYZE searches` runs after each batch cycle.

---

### Stale Data Detection and Refresh Strategy

**Price data:** A price entry is stale when `captured_at` is older than the source's `scrape_frequency_minutes`. Stale products are re-scraped in priority order: first, products with high recent search counts from `mv_popular_products`; then, products with comparison summaries expiring within 30 minutes; then all remaining stale products in FIFO order.

**Comparison summaries:** When `expires_at < NOW()`, the expired summary is served immediately with a staleness notice while async regeneration is enqueued. Once regenerated, the new summary is written to the database and the Redis key is invalidated.

**Product metadata:** Product names, images, and specifications are verified against source data during each price scrape. Detected deltas are queued for review before the `products` row is updated.

---

## Redis Caching Strategy

**Redis version:** 7.2
**Deployment:** Redis Cluster with 3 primary shards and 3 replicas (one replica per primary)
**Eviction policy:** `allkeys-lru`
**Max memory:** 4 GB

All cache keys follow the convention: `sc:{entity}:{identifier}:{variant}` where `sc` is the application namespace prefix.

---

### What to Cache

**Recent Search Results**
- Key: `sc:search:results:{sha256_of_normalized_query_and_filters}`
- Value: JSON array of product IDs with rank, relevance score, and price snapshot
- TTL: 15 minutes

**Current Product Prices (per product, all sources)**
- Key: `sc:prices:current:{product_id}`
- Value: JSON object mapping `source_id` to price, availability, URL, and captured_at
- TTL: 5 minutes (aligned with `mv_current_prices` refresh)

**Comparison Summaries**
- Key: `sc:comparison:{product_id}`
- Value: Full JSON of the `comparison_summaries` row including highlights, recommendation, price_snapshot, and expires_at
- TTL: Computed as `max(0, expires_at - NOW())` at write time — matches database expiry

**Product Detail**
- Key: `sc:product:{product_id}`
- Value: Serialized JSON of the `products` row, excluding `description_tsv`
- TTL: 60 minutes

**Alternative Models**
- Key: `sc:alternatives:{product_id}:{relationship_type}`
- Value: JSON array of top 10 alternatives with similarity_score, note, and relationship_type
- TTL: 24 hours

**Popular Products List**
- Key: `sc:popular:{category}` (category = 'all' for the global list)
- Value: JSON array of top 50 products with denormalized name, brand, lowest price, and rank
- TTL: 30 minutes (aligned with `mv_popular_products` refresh)

**Active Sources Directory**
- Key: `sc:sources:active`
- Value: JSON array of all active sources with source_id, name, logo_url, base_url
- TTL: 6 hours

**AI API Response Cache**
- Key: `sc:ai:response:{sha256_of_prompt_and_model_version}`
- Value: Raw AI API response JSON
- TTL: 4 hours (matches `comparison_summaries.expires_at` default)

---

### Cache Invalidation Rules

| Key Pattern | Trigger | Method |
|---|---|---|
| `sc:search:results:*` | None | TTL expiry only |
| `sc:prices:current:{product_id}` | New `price_entries` row for this product | Pub/Sub event -> DEL |
| `sc:comparison:{product_id}` | New `comparison_summaries` row written | Synchronous DEL after DB write |
| `sc:product:{product_id}` | `products` row updated | Synchronous DEL after DB update |
| `sc:alternatives:{product_id}:*` | `product_alternatives` row inserted/updated | SCAN + DEL per shard |
| `sc:popular:{category}` | None; proactive warm after MV refresh | TTL expiry + warm job |
| `sc:sources:active` | `sources` row inserted/updated | Synchronous DEL after DB write |
| `sc:ai:response:*` | None | TTL expiry only |

**Note on pattern-based invalidation:** `sc:alternatives:{product_id}:*` uses Redis SCAN (never KEYS) to avoid blocking. In the cluster deployment, `{product_id}` is used as a hash tag in the key so all relationship-type variants for a product are co-located on the same shard, making the SCAN a single-shard operation.

---

### TTL Settings Reference

| Data Type | TTL | Rationale |
|---|---|---|
| Search results | 15 minutes | Prices and rankings change; stale results harm trust |
| Current prices | 5 minutes | Aligned with MV refresh; acceptable price delay |
| Comparison summaries | Dynamic (match DB expires_at) | AI generation cost justifies matching DB lifetime |
| Product detail | 60 minutes | Low change frequency; high read frequency |
| Alternative models | 24 hours | AI re-evaluation runs weekly; cache is safe for a day |
| Popular products | 30 minutes | Aligned with MV refresh |
| Active sources | 6 hours | Near-static data; short enough to propagate outages quickly |
| AI API responses | 4 hours | Prevents duplicate AI API calls within a summary lifecycle |

---

## Operational Checklist

### Pre-Launch

- All tables created with correct column types, constraints, and defaults
- All indexes created and verified
- `price_entries` partitioning verified: parent table, current month partition, and next month partition exist
- PgBouncer configured and connection routing tested for both write and read pools
- Streaming replication confirmed with `pg_stat_replication`
- Replication lag alert configured: alert if lag exceeds 30 seconds
- Automated backup (pg_basebackup + WAL archiving) configured with 5-minute RPO
- Backup restore tested in staging: restore completed in under 30 minutes
- Redis Cluster health confirmed: all primary and replica nodes reachable
- All TTLs and invalidation logic tested with integration tests
- `mv_current_prices` and `mv_monthly_price_stats` successfully refreshed and queryable
- pg_cron jobs scheduled: partition creation, MV refresh, cleanup jobs
- Slow query logging enabled: `log_min_duration_statement = 500ms`
- `pg_stat_statements` extension enabled
- `autovacuum` settings reviewed for high-churn tables (`price_entries`, `searches`)

### Ongoing Operations

- Monthly: review `pg_stat_user_indexes` and drop unused indexes
- Monthly: verify partition creation job ran and next month's partition exists
- Monthly: confirm backup restore test was executed and documented
- Quarterly: run disaster recovery failover test
- Quarterly: audit `sources.reliability_score` and investigate sources below 0.80
- Quarterly: review `mv_popular_products` trends for capacity forecasting
- Annually: review data retention tiers and adjust based on storage costs and query patterns
