# Shopping Companion — Performance Architecture

**Document version:** 1.0
**Date:** 2026-03-15
**Scope:** AI-powered Shopping Companion Docker application

---

## Table of Contents

1. [Overview and Performance Targets](#1-overview-and-performance-targets)
2. [Performance Architecture](#2-performance-architecture)
3. [Search Performance](#3-search-performance)
4. [Frontend Performance](#4-frontend-performance)
5. [Backend Performance](#5-backend-performance)
6. [Monitoring and Metrics](#6-monitoring-and-metrics)
7. [Load Testing Strategy](#7-load-testing-strategy)
8. [Capacity Planning](#8-capacity-planning)

---

## 1. Overview and Performance Targets

### 1.1 System Summary

The Shopping Companion is a real-time price comparison application that fans out concurrent searches across multiple external web sources, aggregates results through an AI ranking layer, and streams progressive updates to connected clients via WebSocket. Every architectural decision must be evaluated against its measurable impact on end-user perceived latency.

### 1.2 Service Level Objectives (SLOs)

| Metric | Target | Critical Threshold |
|---|---|---|
| Time to first result (p50) | < 1.5 s | 3 s |
| Time to first result (p95) | < 3.0 s | 5 s |
| Full comparison completion (p50) | < 6 s | 10 s |
| Full comparison completion (p95) | < 10 s | 15 s |
| WebSocket connection establishment | < 200 ms | 500 ms |
| Cache hit response time | < 50 ms | 150 ms |
| Search availability | 99.5% | 99.0% |
| Error rate (5xx) | < 0.5% | 1.0% |

### 1.3 Performance Budget Allocation

The 3-second initial result budget is allocated across pipeline stages:

```
DNS + TLS + WebSocket handshake      50 ms
AI query parsing and enrichment     100 ms
Search fan-out dispatch              20 ms
Fastest source response             800 ms
AI result ranking (first batch)     150 ms
WebSocket frame serialization        30 ms
Network transmission to client       50 ms
Browser render                      100 ms
-----------------------------------------
Total budget consumed             1,300 ms
Remaining headroom                1,700 ms
```

The 1,700 ms of headroom absorbs variability in source response times and network jitter. Sources that respond within 1,300 ms contribute to the first result frame. Sources that respond later contribute to subsequent progressive frames.

---

## 2. Performance Architecture

### 2.1 System Architecture Diagram

```
Client (Browser)
      |
      | WebSocket (persistent)
      |
[Nginx Reverse Proxy + TLS Termination]
      |
[WebSocket Gateway Service]
      |
[Search Orchestrator]
    / | \
   /  |  \
[Source   [Source   [Source
 Worker]   Worker]   Worker]
   |         |         |
[HTTP      [HTTP      [HTTP
 Pool]      Pool]      Pool]
   |         |         |
External   External  External
 Source 1   Source 2  Source N
      \       |       /
       \      |      /
  [Result Aggregator + AI Ranker]
              |
       [Redis Cache Layer]
              |
      [PostgreSQL Database]
```

### 2.2 Concurrency Model

The application is built on a fully asynchronous, non-blocking I/O model throughout every layer of the stack. No thread should block on network I/O, database access, or cache lookups. The concurrency model has three tiers.

**Tier 1 — I/O Concurrency.** All outbound HTTP requests to external sources, all Redis operations, and all database queries execute concurrently within a single async event loop using cooperative multitasking (async/await). This eliminates the overhead of thread context switching for I/O-bound work.

**Tier 2 — CPU Parallelism.** AI ranking, result deduplication, and price normalization are CPU-bound tasks. These execute in a dedicated worker process pool isolated from the I/O event loop. The worker pool size is set to match the number of available CPU cores minus one reserved for the I/O event loop.

**Tier 3 — Horizontal Scaling.** Multiple instances of the Search Orchestrator run behind the WebSocket Gateway. Each instance handles its own fan-out and streams results back through the gateway to the correct client connection.

### 2.3 Caching Architecture

The caching strategy uses two layers with distinct invalidation policies.

**Layer 1 — Redis (Hot Cache).** Stores serialized search result payloads keyed by a normalized search hash. This layer serves repeated searches for the same product within a short window, eliminating all external source requests.

| Cache Type | TTL | Eviction Policy | Key Structure |
|---|---|---|---|
| Search result (exact) | 5 minutes | LRU | `search:{normalized_query_hash}` |
| Search result (category) | 2 minutes | LRU | `search:cat:{category}:{sort}` |
| Source availability | 30 seconds | LRU | `source:{source_id}:status` |
| Exchange rates / normalization | 1 hour | LRU | `fx:{currency_pair}` |
| AI enrichment (parsed query) | 10 minutes | LRU | `ai:parse:{query_hash}` |

**Layer 2 — Database Query Cache.** The PostgreSQL query cache handles product metadata, historical price records, and merchant trust scores. These are read-heavy, write-rarely workloads with longer acceptable staleness windows (15–60 minutes).

**Cache Warming Strategy.** On application startup, the top 500 most-searched product queries from the previous 7 days are pre-populated into Redis to eliminate cold-start latency on deployment.

**Cache Invalidation Rules.** Source result caches are invalidated immediately when a source returns an HTTP error or timeout. Price data caches are invalidated when a price change exceeding 5% is detected, preventing stale pricing from misleading users.

### 2.4 Data Flow for a Single Search Request

```
1.  Client sends search query over WebSocket
2.  Gateway validates and routes to Orchestrator instance
3.  Orchestrator computes normalized query hash
4.  Redis GET: check for exact cache hit
    a. Cache HIT  -> deserialize, stream to client, done
    b. Cache MISS -> proceed to step 5
5.  Dispatch concurrent HTTP requests to all enabled sources
6.  AI query parser enriches the query (brand, model, attributes)
    (runs concurrently with step 5)
7.  As each source responds:
    a. Validate and normalize result schema
    b. Deduplicate against already-received results
    c. AI ranker scores the batch
    d. Stream progressive WebSocket frame to client
8.  Source timeout fires for any non-responding sources (partial results accepted)
9.  Final aggregation: merge all received results, re-rank complete set
10. Stream final WebSocket frame with complete result set
11. Write complete result to Redis with TTL
12. Write search event and price observations to PostgreSQL (async, non-blocking)
```

---

## 3. Search Performance

### 3.1 Parallel Source Querying Strategy

All source queries are dispatched simultaneously. No source query waits for another to complete. The orchestrator maintains a registry of all configured sources with their current health status and adjusts the active source list dynamically.

**Source Registry Properties (per source):**

| Property | Description |
|---|---|
| `base_timeout_ms` | Per-source configurable timeout |
| `p95_response_time_ms` | Rolling 5-minute p95, updated continuously |
| `success_rate_1m` | Rolling 1-minute success rate |
| `circuit_breaker_state` | CLOSED / OPEN / HALF-OPEN |
| `priority_weight` | Influences result ranking when scores are tied |
| `rate_limit_remaining` | Tracks API quota to avoid 429 responses |

**Source Dispatch Order.** All sources are dispatched in the same async batch with no artificial ordering. The event loop handles all concurrent connections without waiting for any individual source.

### 3.2 Timeout Management

Timeouts are managed at three levels to prevent slow sources from blocking the user experience.

**Level 1 — Per-Source Timeout.** Each source has a configurable individual timeout, defaulting to 4 seconds. This is tuned per source based on observed p95 response times. A source that consistently responds in 600 ms gets a 2-second timeout; a source that occasionally spikes to 3 seconds gets a 5-second timeout.

**Level 2 — Progressive Result Deadline.** The first WebSocket frame containing at least one result must be sent within 3 seconds regardless of remaining pending source requests. At the 3-second mark, any results received so far are ranked and streamed even if only one source has responded.

**Level 3 — Hard Search Deadline.** At 10 seconds, the search is finalized unconditionally. Any source responses received after this point are dropped. The client receives a final WebSocket frame marked as complete.

**Timeout Configuration Matrix:**

| Source Category | Base Timeout | Max Tolerated p95 | Circuit Break Threshold |
|---|---|---|---|
| Tier 1 (primary, high reliability) | 3,000 ms | 2,500 ms | 3 failures / 10 requests |
| Tier 2 (secondary, moderate reliability) | 5,000 ms | 4,000 ms | 5 failures / 10 requests |
| Tier 3 (supplemental, best-effort) | 7,000 ms | 6,000 ms | 3 failures / 5 requests |

### 3.3 Progressive Result Delivery

Results are delivered to the client in up to four progressive frames over WebSocket, eliminating the perception of a blank screen while the full comparison is assembled.

**Frame Schedule:**

| Frame | Trigger Condition | Content |
|---|---|---|
| Frame 0 (skeleton) | Immediately on search dispatch | UI skeleton / loading state signal |
| Frame 1 (first results) | First source responds OR 1.5 s elapses | Ranked results from fastest sources |
| Frame 2 (intermediate) | 50% of sources responded OR 4 s elapses | Expanded ranked results |
| Frame 3 (complete) | All sources responded OR 10 s hard deadline | Final ranked complete result set |

Each frame includes an `is_complete` boolean and a `sources_pending` count so the frontend can display an accurate progress indicator without polling.

### 3.4 Request Deduplication

When multiple clients submit identical or near-identical search queries within a short window, the orchestrator collapses them into a single fan-out operation and multicasts results to all waiting clients.

**Deduplication Mechanism:**

1. On receiving a search query, the orchestrator computes a normalized query hash (lowercased, stop words removed, stemmed).
2. The orchestrator checks an in-memory deduplication registry (keyed by query hash, TTL 30 seconds).
3. If an identical search is already in-flight, the new client is registered as a subscriber to that search session rather than initiating a new fan-out.
4. As progressive frames arrive, they are broadcast to all subscribed clients simultaneously.
5. When the search completes, all subscriber registrations are cleared.

This deduplication operates at the process level. In a multi-instance deployment, Redis Pub/Sub propagates in-flight search notifications across Orchestrator instances, ensuring deduplication works horizontally.

**Deduplication Key Normalization Rules:**

- Convert to lowercase
- Trim leading and trailing whitespace
- Collapse multiple spaces to a single space
- Remove common stop words (the, a, an, for, with)
- Sort attribute tokens alphabetically (e.g., "red 64gb iPhone" becomes "64gb iphone red")
- Preserve brand names and model numbers verbatim

---

## 4. Frontend Performance

### 4.1 Code Splitting and Lazy Loading

The frontend application is split into chunks aligned with user navigation paths. The critical path for initial page load contains only the search input component, WebSocket client, and skeleton result list. All other modules load lazily after the initial paint.

**Bundle Structure:**

| Chunk | Load Trigger | Contents |
|---|---|---|
| `core` | Always (initial load) | Router, WebSocket client, search input, skeleton UI |
| `results` | On first search initiation | Result card components, price comparison grid, sort/filter controls |
| `product-detail` | On result card click | Expanded product view, price history chart, merchant details |
| `ai-assistant` | On AI chat panel open | Chat interface, query suggestion engine |
| `account` | On account icon click | Login, saved searches, price alerts |
| `admin` | On admin route | Performance dashboard, source configuration |

**Lazy Loading Policy.** Route-level code splitting ensures each page boundary is a split point. Component-level splitting is applied to any component exceeding 50 KB compiled size. Heavy third-party libraries (charting, rich text) are dynamically imported at point of use.

### 4.2 Optimistic UI Updates

The UI applies optimistic updates to eliminate perceived latency for user interactions that modify local state before server confirmation is received.

**Optimistic Update Scenarios:**

| User Action | Optimistic Response | Rollback Condition |
|---|---|---|
| Save product to wishlist | Immediately show filled heart icon | Server returns error or timeout |
| Set price alert | Immediately show alert active state | Server returns validation error |
| Apply sort/filter to results | Immediately reorder visible results client-side | Server returns different sorted set |
| Dismiss a result | Immediately remove card from list | Server fails to persist preference |

For search initiation, the skeleton frame (Frame 0) is displayed within 16 ms of the user pressing search, before the WebSocket message has been transmitted. This eliminates visible latency between user action and visual feedback.

### 4.3 Virtual Scrolling for Large Result Sets

A search may return hundreds of price comparison results across all sources. Rendering all result cards simultaneously causes DOM bloat, layout thrashing, and scroll jank. Virtual scrolling solves this by rendering only the visible viewport plus a small overscan buffer.

**Virtual Scroll Configuration:**

| Parameter | Value | Rationale |
|---|---|---|
| Item height | Fixed 120 px (collapsed) / 240 px (expanded) | Fixed heights eliminate measurement cost |
| Visible window | Viewport height / item height | Exact count of visible items |
| Overscan above | 5 items | Prevents flash of empty space on fast upward scroll |
| Overscan below | 10 items | Larger buffer for downward scroll (more common) |
| Recycled DOM nodes | Max 40 nodes in pool | Caps memory usage regardless of result count |
| Scroll event throttle | 16 ms (one frame) | Prevents layout thrashing |

When progressive result frames arrive via WebSocket while the user is scrolling, new items are appended to the virtual list's data array without triggering a full re-render. Only newly visible items entering the viewport are rendered.

### 4.4 Image Optimization for Product Thumbnails

**Image Delivery Strategy:**

| Technique | Implementation |
|---|---|
| Responsive images | `srcset` with 3 breakpoints: 80 px, 160 px, 320 px |
| Format selection | WebP with JPEG fallback via `<picture>` element |
| Lazy loading | Native `loading="lazy"` for below-fold images |
| Placeholder | Low-quality image placeholder (LQIP) displayed until full image loads |
| Caching | CDN edge caching with 7-day max-age, immutable for versioned URLs |
| Compression | 80% quality WebP, 85% quality JPEG |
| Dimensions | Always explicitly declared to prevent layout shift (CLS = 0) |

**Thumbnail Processing Pipeline.** Source thumbnails from external sources are proxied through an image optimization service rather than served directly. This service resizes, converts to WebP, and caches optimized versions. Serving directly from external sources is avoided because it introduces uncontrolled latency and bypasses CDN caching.

---

## 5. Backend Performance

### 5.1 Connection Pooling

Maintaining persistent connection pools eliminates the latency of establishing new connections per operation. All three connection types — database, Redis, and outbound HTTP — use pooling.

**PostgreSQL Connection Pool:**

| Parameter | Value | Rationale |
|---|---|---|
| Minimum pool size | 5 connections | Ready immediately on startup |
| Maximum pool size | 20 connections | Prevents database overload; sized for 4 app instances |
| Connection timeout | 5,000 ms | Fail fast rather than queue indefinitely |
| Idle timeout | 10 minutes | Release unused connections to free database resources |
| Max connection lifetime | 30 minutes | Prevent stale connections after database restarts |
| Health check interval | 60 seconds | Detect and replace dead connections proactively |

**Redis Connection Pool:**

| Parameter | Value | Rationale |
|---|---|---|
| Minimum pool size | 3 connections | Covers concurrent GET/SET/PUBLISH operations |
| Maximum pool size | 10 connections | Redis is fast; fewer connections needed than PostgreSQL |
| Connection timeout | 1,000 ms | Redis failures must fail fast to avoid blocking searches |
| Idle timeout | 5 minutes | Redis connections are lightweight |

**Outbound HTTP Connection Pool (per source):**

| Parameter | Value | Rationale |
|---|---|---|
| Connections per source | 5 persistent connections | Handles concurrent searches hitting the same source |
| Total pool size | sources x 5 | Scales with source count |
| Keep-alive timeout | 30 seconds | Match typical server-side keep-alive window |
| Max requests per connection | 100 | Recycle connections to prevent server-side issues |
| DNS cache TTL | 30 seconds | Avoid repeated DNS lookups for static source endpoints |

### 5.2 Async I/O Throughout the Pipeline

The async I/O requirement applies to every operation in the search pipeline without exception.

**Mandatory Async Operations:**

- All database reads and writes use async database drivers. No synchronous ORM calls.
- All Redis operations use async Redis clients. No blocking commands (BLPOP, WAIT) on the main event loop.
- All outbound HTTP requests use an async HTTP client with connection pooling.
- All WebSocket writes are non-blocking. Backpressure is handled by dropping frames if the client buffer exceeds a defined threshold rather than blocking the sender.
- File I/O (logging, configuration reads) uses async file system APIs.
- All inter-process communication with the AI worker pool uses async message passing, never synchronous blocking calls.

**Blocking Operation Prohibition.** Any operation that blocks the event loop for more than 5 ms is considered a defect. This threshold is enforced by event loop lag monitoring (see Section 6). Common blocking operations that must be moved off the event loop include JSON serialization of large payloads, regex matching against large text, and cryptographic operations — all moved to the worker pool.

### 5.3 Worker Pool Sizing

**AI Ranking Worker Pool:**

CPU-bound AI ranking and query parsing operations run in a separate worker process pool. Pool size determines maximum CPU parallelism for these operations.

| Environment | Pool Size Formula | Minimum | Maximum |
|---|---|---|---|
| Development (2-core) | cores - 1 | 1 | 1 |
| Production small (4-core) | cores - 1 | 2 | 3 |
| Production medium (8-core) | cores - 1 | 4 | 7 |
| Production large (16-core) | cores - 2 | 8 | 14 |

**Worker Pool Queue Management:**

| Parameter | Value |
|---|---|
| Max queue depth | 100 tasks |
| Queue full behavior | Reject with 503 (caller falls back to unranked results) |
| Task timeout in queue | 2,000 ms (dropped if not picked up within window) |

Rejecting rather than queuing indefinitely ensures that under extreme load, users receive unranked results immediately rather than ranked results after a long delay.

### 5.4 Memory Management for Large Search Results

A search returning results from 20 sources with 50 products each produces 1,000 result objects in memory simultaneously. Uncontrolled memory growth leads to GC pauses and OOM conditions.

**Memory Constraints and Strategies:**

| Strategy | Description |
|---|---|
| Result count cap | Maximum 500 results retained per search session; lower-scored results discarded |
| Streaming serialization | WebSocket frames are serialized and written to the socket buffer in chunks, not assembled as a single large string |
| Result object pooling | Result objects are allocated from a pool and returned after the search completes, reducing GC pressure |
| Weak references for subscriber lists | WebSocket subscriber lists for deduplication use weak references so disconnected clients do not leak memory |
| Search session TTL | In-memory search session state is evicted after 30 seconds regardless of client connection state |
| Per-process memory limit | Each application process is hard-limited to 512 MB RSS via container resource limits |

**Garbage Collection Tuning.** GC pause duration is monitored as a key metric. If p99 GC pause exceeds 50 ms, the following mitigations are evaluated in order: reduce result object allocation rate, increase GC frequency to reduce per-cycle work, reduce per-process memory limit to force earlier collection.

---

## 6. Monitoring and Metrics

### 6.1 Key Performance Indicators

**Search Latency KPIs:**

| KPI | Collection Method | Alert Threshold | Critical Threshold |
|---|---|---|---|
| Time to first frame (p50) | Instrumented in Orchestrator | > 2,000 ms | > 3,000 ms |
| Time to first frame (p95) | Instrumented in Orchestrator | > 2,500 ms | > 5,000 ms |
| Full search completion (p50) | Instrumented in Orchestrator | > 5,000 ms | > 10,000 ms |
| Full search completion (p95) | Instrumented in Orchestrator | > 8,000 ms | > 15,000 ms |
| Search error rate | Counter / total searches | > 1% | > 5% |
| Search abandonment rate | WebSocket disconnect before Frame 3 | > 10% | > 25% |

**Source Response Time KPIs (per source):**

| KPI | Collection Method | Alert Threshold |
|---|---|---|
| Source p50 response time | Instrumented per HTTP request | > 80% of source timeout |
| Source p95 response time | Instrumented per HTTP request | > 90% of source timeout |
| Source timeout rate | Timed-out requests / total | > 5% |
| Source error rate | 4xx + 5xx / total | > 10% |
| Circuit breaker state | State machine events | Any OPEN state |

**Cache Performance KPIs:**

| KPI | Collection Method | Alert Threshold |
|---|---|---|
| Redis cache hit rate | Hits / (hits + misses) | < 40% |
| Redis operation latency (p95) | Instrumented per operation | > 10 ms |
| Redis memory utilization | Redis INFO stats | > 80% max memory |
| Redis eviction rate | Redis INFO evicted_keys | > 100 / minute |
| DB query cache hit rate | PostgreSQL pg_stat_statements | < 60% |

**Infrastructure KPIs:**

| KPI | Collection Method | Alert Threshold |
|---|---|---|
| Event loop lag (p95) | Sampled every 100 ms | > 50 ms |
| GC pause duration (p99) | Runtime GC hooks | > 100 ms |
| Worker pool queue depth | In-process gauge | > 50 tasks |
| Worker pool utilization | Busy workers / total workers | > 80% |
| WebSocket connection count | Gauge per gateway instance | > 10,000 |
| Active search sessions | Gauge per orchestrator instance | > 500 |

### 6.2 Health Check Endpoints

| Endpoint | Method | Response Time SLO | Purpose |
|---|---|---|---|
| `GET /health/live` | HTTP 200 / 503 | < 50 ms | Liveness: is the process alive and event loop responsive |
| `GET /health/ready` | HTTP 200 / 503 | < 200 ms | Readiness: are dependencies (Redis, DB) reachable |
| `GET /health/sources` | HTTP 200 / JSON | < 500 ms | Source availability: status of each external source |
| `GET /metrics` | HTTP 200 / Prometheus text | < 100 ms | Prometheus scrape endpoint for all KPIs |

**Liveness Check Logic.** The liveness endpoint responds HTTP 200 only when the event loop lag measured in the last 5 seconds is below 500 ms. If the event loop is blocked, this endpoint will itself be slow to respond, signaling the orchestrator to restart the instance.

**Readiness Check Logic.** The readiness endpoint performs a lightweight Redis PING and a PostgreSQL `SELECT 1`. It returns HTTP 200 only when both succeed within 100 ms. A non-ready instance is removed from the load balancer rotation until it recovers.

### 6.3 Resource Utilization Monitoring

Resource metrics are collected at 15-second intervals and retained for 90 days.

**Container-Level Metrics:**

| Metric | Source | Alert Threshold |
|---|---|---|
| CPU utilization | Container runtime cgroups | > 80% sustained 5 min |
| Memory RSS | Container runtime cgroups | > 80% of limit |
| Memory working set | Container runtime cgroups | > 70% of limit |
| Network bytes in/out | Container runtime | Baseline + 3 standard deviations |
| Open file descriptors | `/proc/{pid}/fd` | > 70% of system limit |
| TCP connection count | Container stats | > 10,000 |

**Application-Level Metrics:**

| Metric | Granularity | Retention |
|---|---|---|
| Searches per second | 1 minute | 90 days |
| Search latency histogram | 1 minute | 90 days |
| Source response time histogram | 1 minute | 90 days |
| Cache hit/miss counters | 1 minute | 90 days |
| Worker pool queue depth | 15 seconds | 30 days |
| WebSocket connection count | 15 seconds | 30 days |
| Error rates by category | 1 minute | 90 days |

---

## 7. Load Testing Strategy

### 7.1 Expected Usage Patterns

**Baseline Traffic Model:**

| Period | Searches / Minute | Concurrent WebSocket Connections | Notes |
|---|---|---|---|
| Night (00:00–08:00) | 10–30 | 20–60 | Background activity |
| Morning (08:00–12:00) | 80–150 | 150–300 | Morning shopping research |
| Afternoon (12:00–17:00) | 120–200 | 250–400 | Peak weekday usage |
| Evening (17:00–22:00) | 200–350 | 400–700 | Primary peak window |
| Weekend peak | 300–500 | 600–1,000 | Highest sustained load |
| Flash sale event | 1,500–3,000 | 3,000–6,000 | Spike scenario |

**Search Query Distribution:**

| Query Type | Percentage | Characteristics |
|---|---|---|
| Exact product model search | 35% | High cache hit potential |
| Category + attribute search | 40% | Lower cache hit rate |
| Brand-only search | 15% | Broad results, high result count |
| Comparison (two products) | 10% | Double fan-out required |

**Session Behavior Model:**

- Average searches per session: 3.2
- Average think time between searches: 45 seconds
- Average WebSocket session duration: 8 minutes
- Percentage of sessions that apply filters: 60%
- Percentage of sessions that view product detail: 45%

### 7.2 Load Test Scenarios

**Scenario 1 — Baseline Load Test**

Purpose: Establish performance baseline and confirm SLOs are met under normal load.

| Parameter | Value |
|---|---|
| Virtual users | 200 |
| Ramp-up duration | 5 minutes |
| Sustained duration | 30 minutes |
| Ramp-down | 2 minutes |
| Target searches/minute | 150 |
| Success criteria | p95 first frame < 3 s, error rate < 0.5% |

**Scenario 2 — Peak Load Test**

Purpose: Confirm SLOs are met at maximum expected normal load.

| Parameter | Value |
|---|---|
| Virtual users | 1,000 |
| Ramp-up duration | 10 minutes |
| Sustained duration | 30 minutes |
| Ramp-down | 5 minutes |
| Target searches/minute | 500 |
| Success criteria | p95 first frame < 3 s, p95 full search < 10 s, error rate < 1% |

**Scenario 3 — Spike Test (Flash Sale Simulation)**

Purpose: Assess system behavior during a sudden 10x traffic surge and verify graceful degradation.

| Parameter | Value |
|---|---|
| Baseline virtual users | 200 |
| Spike virtual users | 2,000 (added within 60 seconds) |
| Spike duration | 10 minutes |
| Acceptable degradation | Increased latency; error rate must stay < 5% |
| Recovery criteria | Return to baseline latency within 3 minutes of spike end |

**Scenario 4 — Soak Test**

Purpose: Detect memory leaks, connection pool exhaustion, and performance degradation over time.

| Parameter | Value |
|---|---|
| Virtual users | 400 |
| Duration | 8 hours |
| Searches/minute | 250 |
| Success criteria | No more than 10% latency increase from hour 1 to hour 8 |
| Memory constraint | RSS must not grow more than 20% over the 8-hour period |

### 7.3 Bottleneck Identification Approach

When test latency exceeds the SLO threshold, diagnosis follows this ordered checklist:

1. **Event loop lag elevated?** CPU-bound work is blocking the event loop. Investigate recent code changes for synchronous blocking operations.

2. **Worker pool queue depth elevated?** CPU worker pool is undersized. Increase pool size or optimize AI ranking algorithms.

3. **Redis operation latency elevated?** Check Redis memory utilization and eviction rate. If evictions are occurring, increase Redis memory allocation or reduce TTLs.

4. **Redis cache hit rate low?** Query normalization may be producing too many distinct keys. Review deduplication logic. Investigate whether traffic is dominated by unique low-frequency queries.

5. **Source response times elevated?** External sources are degraded. Check circuit breaker states. Consider reducing per-source timeout to shed slow sources faster.

6. **Database connection pool exhausted?** Pool size is insufficient for concurrency level. Increase pool maximum or investigate slow queries holding connections.

7. **Network bandwidth saturated?** Result payload sizes are too large. Enforce result count caps and verify compression settings.

**Load Test Tooling Requirements:**

| Requirement | Purpose |
|---|---|
| WebSocket protocol support | Test WebSocket connections, not HTTP polling |
| Progressive frame capture | Record timing of each WebSocket frame, not just final response |
| Source simulation capability | Mock slow and failing sources to exercise timeout behavior |
| Distributed test execution | Drive high virtual user counts from multiple test nodes |
| Real-time metric correlation | View application metrics alongside test metrics simultaneously |

### 7.4 Scaling Triggers

**Scale-Out Triggers (add Orchestrator instance):**

| Metric | Threshold | Cooldown |
|---|---|---|
| CPU utilization | > 70% sustained 3 minutes | 5 minutes |
| Active search sessions | > 400 per instance | 3 minutes |
| Event loop lag p95 | > 30 ms sustained 2 minutes | 5 minutes |
| Worker pool queue depth | > 30 tasks sustained 1 minute | 3 minutes |

**Scale-In Triggers (remove Orchestrator instance):**

| Metric | Threshold | Cooldown |
|---|---|---|
| CPU utilization | < 30% sustained 10 minutes | 15 minutes |
| Active search sessions | < 100 per instance sustained 10 minutes | 15 minutes |

**In-Process Mitigations Before Scaling.** Before triggering a scale-out, the system applies these mitigations to absorb temporary spikes:

- Increase Redis cache TTL from 5 minutes to 10 minutes to raise cache hit rate
- Reduce per-source timeout to a uniform 3-second maximum to shed slow sources faster
- Reduce maximum result count per search from 500 to 200 to reduce AI ranking work
- Enable request coalescing for identical concurrent searches with aggressive normalization

---

## 8. Capacity Planning

### 8.1 Resource Sizing per Instance

| Resource | Development | Production (per instance) |
|---|---|---|
| CPU | 1 core | 4 cores |
| Memory | 512 MB | 2 GB |
| Orchestrator instances | 1 | 2–8 (auto-scaling) |
| Redis memory | 256 MB | 4 GB |
| PostgreSQL connections | 5 | 20 |

### 8.2 Scaling Envelope

The architecture supports linear horizontal scaling up to 8 Orchestrator instances before requiring architectural changes. This envelope supports approximately 4,000 concurrent searches per minute, well above the flash sale spike scenario of 3,000 searches per minute.

Beyond 8 instances, the following architectural upgrades are required in priority order:

1. Redis Cluster (shard keyspace across 3 Redis primary nodes)
2. PostgreSQL read replicas (direct read queries to replicas)
3. Search fan-out sharding (partition sources across Orchestrator instances to reduce per-instance outbound connection count)
4. WebSocket Gateway horizontal scaling with consistent hashing for session affinity

### 8.3 Growth Projections and Review Cadence

Performance architecture is reviewed quarterly against actual usage growth. Each review evaluates whether the current instance count and resource allocation can support the projected load 6 months forward. Capacity is provisioned to handle 2x current peak load at all times, providing headroom for unexpected growth and flash events without requiring emergency scaling actions.

---

*This document is the authoritative reference for performance architecture decisions on the Shopping Companion application. All performance-related implementation decisions must be traceable to targets and strategies defined here. Deviations require explicit documentation of the rationale and updated metric targets.*
