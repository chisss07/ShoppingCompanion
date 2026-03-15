# Shopping Companion -- System Architecture

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Microservices Architecture](#2-microservices-architecture)
3. [Inter-Service Communication](#3-inter-service-communication)
4. [Architecture Patterns](#4-architecture-patterns)
5. [Security Architecture](#5-security-architecture)
6. [Scalability Design](#6-scalability-design)
7. [Error Handling Strategy](#7-error-handling-strategy)
8. [Data Architecture](#8-data-architecture)
9. [Docker Compose Architecture](#9-docker-compose-architecture)
10. [Observability and Health](#10-observability-and-health)
11. [Architectural Decision Records](#11-architectural-decision-records)

---

## 1. System Overview

The Shopping Companion is an AI-powered product search and price comparison application. A user submits a natural-language shopping query (for example, "best noise-cancelling headphones under $300"), and the system fans out to multiple external sources, aggregates results with AI-assisted ranking, and streams progress back to the browser in real time.

### High-Level Data Flow

```
User Browser
    |
    |  HTTPS (REST + WebSocket upgrade)
    v
+-----------+       +------------------+       +----------------+
|  Frontend |<----->|   Backend API    |<----->|   PostgreSQL   |
|  (React)  |       |   (FastAPI)      |       |   Database     |
+-----------+       +------------------+       +----------------+
                        |          ^
                        |          |  Results / status
              Search    |          |
              request   v          |
                    +--------+     |
                    | Redis  |-----+
                    | Queue  |
                    +--------+
                        |
            +-----------+-----------+
            |           |           |
            v           v           v
       +----------+ +----------+ +----------+
       | Search   | | Search   | | Search   |
       | Worker 1 | | Worker 2 | | Worker N |
       +----------+ +----------+ +----------+
            |           |           |
            v           v           v
      External APIs (retailers, price aggregators, AI providers)
```

### Guiding Principles

- **Loose coupling**: services communicate through Redis queues and events, never through direct function calls or shared databases (with the sole exception of PostgreSQL, which is accessed only by the Backend API).
- **Single responsibility**: each service owns exactly one concern.
- **Graceful degradation**: partial results are always better than no results.
- **Observable by default**: every service emits structured logs, health checks, and metrics.

---

## 2. Microservices Architecture

### 2.1 Frontend Service (React + TypeScript)

| Property | Value |
|---|---|
| Runtime | Node 20 (build) / Nginx (serve) |
| Port | 3000 (dev) / 80 (production Nginx) |
| Depends on | Backend API, WebSocket Server |

**Responsibilities**

- Render the search interface and results display.
- Manage client-side state (search history, user preferences).
- Establish a WebSocket connection to receive real-time search progress.
- Submit search requests to the Backend API via REST.

**Build and Serving Strategy**

In production the React application is compiled to static assets and served by an Nginx container. Nginx also acts as a reverse proxy, routing `/api/*` to the Backend API and `/ws/*` to the WebSocket Server, which eliminates CORS concerns in production.

**Key Technical Decisions**

- TypeScript strict mode enforced project-wide.
- State management via React Context + `useReducer` for search state; no external state library needed at this scale.
- WebSocket reconnection handled with exponential backoff (initial 1 second, max 30 seconds, jitter applied).

---

### 2.2 Backend API Service (Python FastAPI)

| Property | Value |
|---|---|
| Runtime | Python 3.12, uvicorn with multiple workers |
| Port | 8000 |
| Depends on | PostgreSQL, Redis |

**Responsibilities**

- Accept and validate search requests from the frontend.
- Publish search jobs to the Redis task queue.
- Serve historical search results and saved comparisons from PostgreSQL.
- Enforce rate limiting and authentication (if added later).
- Expose REST endpoints only; it does not manage WebSocket connections.

**API Surface**

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/v1/searches` | Submit a new search query; returns a `search_id` |
| GET | `/api/v1/searches/{search_id}` | Retrieve results for a completed or in-progress search |
| GET | `/api/v1/searches` | List recent searches (paginated) |
| DELETE | `/api/v1/searches/{search_id}` | Remove a search and its results |
| GET | `/api/v1/health` | Liveness and readiness probe |

**Database Access**

The Backend API is the sole service permitted to read from and write to PostgreSQL. It uses SQLAlchemy async with a connection pool (min 5, max 20 connections). Search Workers never access PostgreSQL directly; they publish results to Redis, and the Backend API persists them.

---

### 2.3 Search Worker Service (Python)

| Property | Value |
|---|---|
| Runtime | Python 3.12 |
| Port | None (no HTTP interface) |
| Depends on | Redis |
| Scaling | Horizontal -- run N replicas |

**Responsibilities**

- Consume search jobs from the Redis task queue.
- Fan out to multiple external sources (retailer APIs, web scraping endpoints, AI summarization providers).
- Normalize and rank results using AI-assisted scoring.
- Publish progress events and final results back to Redis.

**Processing Pipeline**

```
Job consumed from Redis queue
    |
    v
Parse and validate search parameters
    |
    v
Fan out to external sources (concurrent, with per-source timeout)
    |
    +---> Source A (retailer API)
    +---> Source B (price aggregator)
    +---> Source C (AI-powered web search)
    |
    v
Collect responses (partial results accepted)
    |
    v
Normalize into common product schema
    |
    v
AI ranking and deduplication
    |
    v
Publish results to Redis channel: search:{search_id}:results
Publish status to Redis channel: search:{search_id}:status
```

**External API Interaction**

Each external source call is wrapped in a circuit breaker (see Section 4.2). Workers use `httpx.AsyncClient` with connection pooling. Each source has an independent timeout (default 10 seconds) so that one slow source does not block others.

---

### 2.4 WebSocket Server

| Property | Value |
|---|---|
| Runtime | Python 3.12, uvicorn |
| Port | 8001 |
| Depends on | Redis |

**Responsibilities**

- Accept WebSocket connections from the frontend.
- Subscribe to Redis Pub/Sub channels for active searches.
- Forward progress events and partial results to the connected client in real time.

**Why a Separate Service**

WebSocket connections are long-lived and stateful. Mixing them into the Backend API would couple request-response handling with persistent connection management, making independent scaling impossible. By isolating WebSocket concerns:

- The Backend API can scale based on REST request volume.
- The WebSocket Server can scale based on concurrent connection count.
- A crashed WebSocket Server does not affect API availability.

**Connection Lifecycle**

```
Client connects:  ws://host/ws/searches/{search_id}
    |
    v
Server subscribes to Redis channels:
    - search:{search_id}:status
    - search:{search_id}:results
    |
    v
Server forwards messages as they arrive:
    { "type": "progress", "source": "amazon", "status": "searching" }
    { "type": "partial_result", "products": [...] }
    { "type": "progress", "source": "amazon", "status": "complete" }
    { "type": "complete", "total_results": 24 }
    |
    v
Client disconnects or search completes:
    Server unsubscribes from Redis channels
    Connection closed
```

**Message Schema (WebSocket Frames)**

All messages are JSON with a required `type` field.

| type | Additional fields | Description |
|---|---|---|
| `progress` | `source`, `status`, `message` | A source has changed state |
| `partial_result` | `source`, `products` | Products found so far from one source |
| `complete` | `total_results`, `search_duration_ms` | Search finished |
| `error` | `source`, `error_code`, `message` | A source failed |

---

### 2.5 PostgreSQL Database

| Property | Value |
|---|---|
| Version | PostgreSQL 16 |
| Port | 5432 (internal network only) |
| Accessed by | Backend API only |

**Responsibilities**

- Persist search queries, results, and user history.
- Provide queryable storage for the CQRS read model (see Section 4.1).

**Schema Overview**

```
searches
    id              UUID  PRIMARY KEY
    query_text      TEXT  NOT NULL
    filters         JSONB
    status          VARCHAR(20)  -- pending, processing, completed, failed
    created_at      TIMESTAMPTZ
    completed_at    TIMESTAMPTZ
    result_count    INTEGER

search_results
    id              UUID  PRIMARY KEY
    search_id       UUID  REFERENCES searches(id) ON DELETE CASCADE
    source          VARCHAR(50)
    product_name    TEXT
    price           DECIMAL(10,2)
    currency        VARCHAR(3)
    url             TEXT
    image_url       TEXT
    rating          DECIMAL(3,2)
    review_count    INTEGER
    metadata        JSONB
    ai_score        DECIMAL(5,4)
    created_at      TIMESTAMPTZ

source_health
    source_name     VARCHAR(50)  PRIMARY KEY
    is_healthy      BOOLEAN
    last_success    TIMESTAMPTZ
    last_failure    TIMESTAMPTZ
    failure_count   INTEGER
    circuit_state   VARCHAR(10)  -- closed, open, half_open
```

**Indexing Strategy**

- `searches(created_at DESC)` -- for listing recent searches.
- `searches(status)` -- for monitoring in-progress searches.
- `search_results(search_id, ai_score DESC)` -- for retrieving ranked results.
- `search_results(source)` -- for per-source analytics.
- GIN index on `search_results(metadata)` -- for JSONB queries.

---

### 2.6 Redis

| Property | Value |
|---|---|
| Version | Redis 7 |
| Port | 6379 (internal network only) |
| Accessed by | Backend API, Search Workers, WebSocket Server |

**Three Distinct Roles**

| Role | Mechanism | Purpose |
|---|---|---|
| Task queue | Redis Lists (`LPUSH` / `BRPOP`) | Distribute search jobs to workers |
| Pub/Sub broker | Redis Pub/Sub channels | Stream real-time progress to WebSocket Server |
| Cache | Redis Strings with TTL | Cache repeated search results |

**Key Namespace Convention**

```
queue:searches                           -- List: pending search jobs
search:{search_id}:status               -- Pub/Sub + String: current status
search:{search_id}:results              -- Pub/Sub + String: cached results
cache:search:{normalized_query_hash}    -- String with TTL: cached results for identical queries
circuit:{source_name}                   -- Hash: circuit breaker state
rate_limit:{client_ip}                  -- String with TTL: rate limit counter
```

---

## 3. Inter-Service Communication

### 3.1 Communication Matrix

| From | To | Protocol | Pattern | Data Format |
|---|---|---|---|---|
| Frontend | Backend API | HTTP/1.1 REST | Request-Response | JSON |
| Frontend | WebSocket Server | WebSocket (ws://) | Bidirectional stream | JSON frames |
| Backend API | Redis | Redis protocol | Publish (queue + pub/sub) | JSON-serialized strings |
| Backend API | PostgreSQL | PostgreSQL wire protocol | Query-Response | SQL |
| Search Worker | Redis | Redis protocol | Consume (queue), Publish (pub/sub + cache) | JSON-serialized strings |
| WebSocket Server | Redis | Redis protocol | Subscribe (pub/sub) | JSON-serialized strings |

### 3.2 Search Request Flow (Step by Step)

This is the complete lifecycle of a single search, showing every inter-service message.

```
Step  From               To                  Action
----  ----               --                  ------
 1    Frontend           Backend API         POST /api/v1/searches { "query": "..." }
 2    Backend API        PostgreSQL          INSERT INTO searches (status='pending')
 3    Backend API        Redis               LPUSH queue:searches { search_id, query, filters }
 4    Backend API        Frontend            HTTP 202 Accepted { "search_id": "abc-123" }
 5    Frontend           WebSocket Server    WS CONNECT /ws/searches/abc-123
 6    WebSocket Server   Redis               SUBSCRIBE search:abc-123:status
                                             SUBSCRIBE search:abc-123:results
 7    Search Worker      Redis               BRPOP queue:searches (blocks until job available)
 8    Search Worker      Redis               PUBLISH search:abc-123:status
                                               { "type":"progress", "status":"started" }
 9    Redis              WebSocket Server    Message on search:abc-123:status channel
10    WebSocket Server   Frontend            WS FRAME { "type":"progress", "status":"started" }
11    Search Worker      External APIs       HTTP requests to sources (concurrent)
12    Search Worker      Redis               PUBLISH search:abc-123:results
                                               { "type":"partial_result", "source":"...", ... }
      (Steps 11-12 repeat per source as results arrive)
13    Search Worker      Redis               PUBLISH search:abc-123:status
                                               { "type":"complete", "total_results": 24 }
14    Search Worker      Redis               SET search:abc-123:results <full JSON> EX 3600
15    Search Worker      Redis               LPUSH queue:persist { search_id, results }
16    Backend API        Redis               BRPOP queue:persist (separate listener)
17    Backend API        PostgreSQL          INSERT INTO search_results (batch)
                                             UPDATE searches SET status='completed'
```

### 3.3 Why Not Direct HTTP Between Services

Search Workers do not expose an HTTP interface and the Backend API does not call them directly. This is intentional:

- **Decoupled scaling**: adding more workers requires zero configuration changes in the Backend API.
- **Backpressure**: the Redis queue naturally buffers bursts; the API never blocks waiting for a worker.
- **Fault isolation**: a crashed worker causes its in-progress job to time out and be retried; no cascading failure reaches the API.

---

## 4. Architecture Patterns

### 4.1 CQRS (Command Query Responsibility Segregation)

The system separates write and read paths for search data.

**Command Path (Write)**

```
User submits search
    -> Backend API validates and enqueues (Redis)
    -> Search Worker processes and publishes results (Redis)
    -> Backend API persists to PostgreSQL (async, via persist queue)
```

The command path prioritizes speed. The user receives a `search_id` immediately (Step 4 above) and results stream in via WebSocket. PostgreSQL persistence happens asynchronously after results are available.

**Query Path (Read)**

```
User requests past search
    -> Backend API checks Redis cache
    -> Cache miss: Backend API queries PostgreSQL
    -> Returns results to Frontend
```

The query path reads from the cache first (results are cached for 1 hour) and falls back to PostgreSQL. This path never touches the task queue or Search Workers.

**Why CQRS Here**

- Write and read workloads have fundamentally different performance profiles: writes involve fan-out to external APIs (seconds), while reads are simple lookups (milliseconds).
- Separating them allows the write path to be optimized for throughput (more workers) and the read path for latency (caching, database indexes).

---

### 4.2 Circuit Breaker Pattern

Every external API call in the Search Worker is wrapped in a circuit breaker to prevent cascading failures when a source is down.

**States**

```
CLOSED (normal operation)
    |
    |  failure_count >= threshold (5 failures in 60 seconds)
    v
OPEN (all calls to this source are rejected immediately)
    |
    |  after cooldown period (60 seconds)
    v
HALF_OPEN (allow 1 trial request)
    |
    +---> success: transition to CLOSED, reset failure count
    +---> failure: transition to OPEN, restart cooldown
```

**Implementation Details**

- Circuit state is stored in Redis (`circuit:{source_name}` hash) so all worker replicas share the same circuit state.
- Fields: `state`, `failure_count`, `last_failure_time`, `last_success_time`.
- When a circuit is OPEN, the worker skips that source and publishes an error event so the frontend can display "Source X is temporarily unavailable."
- The `source_health` table in PostgreSQL tracks historical circuit state for operational dashboards.

**Thresholds Per Source**

| Source Type | Failure Threshold | Cooldown Period | Request Timeout |
|---|---|---|---|
| Retailer API | 5 failures / 60s | 60 seconds | 10 seconds |
| Price Aggregator | 3 failures / 60s | 90 seconds | 15 seconds |
| AI Provider | 3 failures / 60s | 120 seconds | 30 seconds |

---

### 4.3 Retry Pattern with Exponential Backoff

Retries are applied at two levels.

**Level 1: External API Calls (within Search Worker)**

When a source returns a transient error (HTTP 429, 500, 502, 503, 504), the worker retries before recording a circuit breaker failure.

```
Attempt 1:  immediate
Attempt 2:  wait  1s + random(0, 0.5s)
Attempt 3:  wait  2s + random(0, 1.0s)
Attempt 4:  wait  4s + random(0, 2.0s)
    (max 4 attempts per source per search)
```

Non-transient errors (HTTP 400, 401, 403, 404) are not retried.

**Level 2: Search Job Queue (system-level)**

If a Search Worker crashes mid-processing, the job must be recovered. This is handled with a visibility timeout pattern:

1. Worker `BRPOP`s from `queue:searches` and simultaneously `LPUSH`es to `queue:processing:{worker_id}`.
2. Worker sets a TTL key `processing:{search_id}` with a 120-second expiry.
3. On successful completion, the worker removes the job from `queue:processing:{worker_id}` and deletes the TTL key.
4. A periodic monitor (running in the Backend API) checks for expired TTL keys. If found, the job is moved back to `queue:searches` with an incremented retry count.
5. After 3 total attempts, the job is moved to `queue:dead_letter` and the search status is set to `failed`.

---

### 4.4 Event-Driven Architecture

The event-driven design centers on Redis as the message backbone. Events flow in a single direction through the system.

**Event Categories**

| Category | Channel Pattern | Publisher | Subscriber(s) |
|---|---|---|---|
| Search lifecycle | `search:{id}:status` | Search Worker | WebSocket Server |
| Partial results | `search:{id}:results` | Search Worker | WebSocket Server |
| Persistence jobs | `queue:persist` | Search Worker | Backend API |
| Circuit state changes | `circuit:events` | Search Worker | Backend API (for logging) |

**Event Envelope**

Every event published to Redis follows a consistent envelope:

```json
{
  "event_id": "evt_a1b2c3d4",
  "event_type": "search.progress",
  "search_id": "abc-123",
  "timestamp": "2026-03-15T12:00:00.000Z",
  "payload": {
    "source": "amazon",
    "status": "complete",
    "result_count": 8
  }
}
```

The `event_id` and `timestamp` fields enable idempotent processing and event ordering on the consumer side.

---

## 5. Security Architecture

### 5.1 API Rate Limiting

Rate limiting is enforced in the Backend API using a sliding window counter stored in Redis.

**Limits**

| Endpoint Pattern | Window | Max Requests | Scope |
|---|---|---|---|
| `POST /api/v1/searches` | 1 minute | 10 | Per IP |
| `GET /api/v1/searches/*` | 1 minute | 60 | Per IP |
| `GET /api/v1/health` | No limit | -- | -- |

**Implementation**

The Backend API uses a FastAPI middleware that, for each incoming request:

1. Computes the key `rate_limit:{client_ip}:{endpoint_group}:{window_id}`.
2. Executes `INCR` on the key and sets a TTL of the window duration if the key is new.
3. If the counter exceeds the limit, returns HTTP 429 with a `Retry-After` header.

**Why Per-IP and Not Per-User**

In the initial version, the application does not require user authentication. Per-IP rate limiting is the appropriate default. When authentication is added, limits should shift to per-user with more generous thresholds, while per-IP limits remain as a secondary defense against abuse from unauthenticated traffic.

### 5.2 Input Sanitization

All user input passes through validation before any processing occurs.

**Search Query Validation (Backend API)**

- Maximum query length: 500 characters.
- Strip HTML tags and script content.
- Reject queries that contain only whitespace or special characters.
- Pydantic model validation with strict types for all request bodies.

**Output Encoding**

- All data returned to the frontend is JSON-encoded by FastAPI's default serializer, which escapes special characters.
- The frontend uses React's built-in XSS protection (JSX auto-escapes rendered values). Raw HTML injection via `dangerouslySetInnerHTML` is prohibited by linting rules.

**Search Worker Input**

- URLs received from external APIs are validated against an allowlist of domains before being stored.
- Price values are parsed and validated as numeric; non-numeric values are discarded.
- Image URLs are validated for HTTPS protocol.

### 5.3 CORS Configuration

**Development**

```
Allowed origins:  http://localhost:3000
Allowed methods:  GET, POST, DELETE, OPTIONS
Allowed headers:  Content-Type, Authorization
Max age:          3600 seconds
```

**Production**

In production, CORS headers are unnecessary because Nginx reverse-proxies all traffic through a single origin. The Backend API and WebSocket Server are not exposed directly. CORS middleware should be disabled or set to the single production domain.

**Nginx Routing (Production)**

```
/              -> Frontend static files (Nginx serves directly)
/api/*         -> Backend API (proxy_pass http://backend:8000)
/ws/*          -> WebSocket Server (proxy_pass http://websocket:8001, with upgrade headers)
```

This single-origin approach eliminates CORS as an attack surface entirely.

### 5.4 Environment Variable Management

**Principles**

- No secret is ever committed to version control.
- All secrets are injected via environment variables at container runtime.
- A `.env.example` file documents every required variable with placeholder values.
- Docker Compose reads from a `.env` file that is listed in `.gitignore`.

**Required Environment Variables**

| Variable | Used By | Description |
|---|---|---|
| `DATABASE_URL` | Backend API | PostgreSQL connection string |
| `REDIS_URL` | Backend API, Search Worker, WebSocket Server | Redis connection string |
| `OPENAI_API_KEY` | Search Worker | AI provider API key |
| `SEARCH_API_KEY` | Search Worker | Web search API key (SerpAPI, Bing, etc.) |
| `SECRET_KEY` | Backend API | Signing key for future auth tokens |
| `ALLOWED_ORIGINS` | Backend API | CORS allowed origins (comma-separated) |
| `LOG_LEVEL` | All services | Logging verbosity (DEBUG, INFO, WARNING, ERROR) |
| `WORKER_CONCURRENCY` | Search Worker | Max concurrent source requests per worker |

**Secret Rotation**

For production deployments beyond Docker Compose (such as Kubernetes or cloud-managed containers), secrets should be sourced from a secrets manager (AWS Secrets Manager, HashiCorp Vault, or similar) rather than environment variables. The application code reads from environment variables regardless; the injection mechanism changes.

### 5.5 Network Security

**Docker Network Isolation**

All services communicate over a single internal Docker bridge network (`shopping-net`). Only Nginx exposes ports to the host machine.

```
Exposed to host:
    Nginx: 80, 443

Internal only (not exposed to host):
    Backend API: 8000
    WebSocket Server: 8001
    PostgreSQL: 5432
    Redis: 6379
```

This means PostgreSQL and Redis are unreachable from outside the Docker network. No firewall rules or external network configuration is needed to protect them in a single-host deployment.

---

## 6. Scalability Design

### 6.1 Horizontal Scaling of Search Workers

Search Workers are stateless consumers of a Redis queue. Scaling them is a matter of increasing the replica count.

```yaml
# In docker-compose.yml
search-worker:
  ...
  deploy:
    replicas: 3
```

**How It Works**

- `BRPOP` on a Redis list is atomic: only one worker receives each job.
- No coordination between workers is required.
- Adding or removing workers requires no configuration changes in any other service.

**Scaling Triggers**

| Metric | Threshold | Action |
|---|---|---|
| Queue depth (`LLEN queue:searches`) | > 10 for 30 seconds | Add worker replicas |
| Worker CPU utilization | > 80% sustained | Add worker replicas |
| Queue depth | 0 for 5 minutes | Safe to remove replicas |

In a Docker Compose context, scaling is manual (`docker compose up --scale search-worker=5`). For production orchestration (Kubernetes, ECS), these triggers can drive a Horizontal Pod Autoscaler or equivalent.

### 6.2 Database Connection Pooling

**Problem**

Each Backend API worker process opens its own database connections. With multiple uvicorn workers and potential future replicas, the connection count can exceed PostgreSQL's default limit (100).

**Solution**

SQLAlchemy async engine with bounded pool:

```
pool_size:        5   (connections per uvicorn worker)
max_overflow:    10   (temporary connections under burst)
pool_timeout:    30   (seconds to wait for a connection before erroring)
pool_recycle:   300   (seconds before a connection is recycled to prevent stale connections)
```

With 4 uvicorn workers, the maximum connection count is `4 * (5 + 10) = 60`, well within PostgreSQL's default limit.

**If Scaling Beyond a Single API Instance**

Add PgBouncer as a connection pooler between the Backend API and PostgreSQL. PgBouncer maintains a small pool of actual PostgreSQL connections and multiplexes application connections onto them. It runs as a sidecar container or a separate service.

### 6.3 Redis Caching Strategy

**What Is Cached**

| Data | Key Pattern | TTL | Invalidation |
|---|---|---|---|
| Completed search results | `cache:search:{query_hash}` | 1 hour | Time-based expiry |
| Source health status | `circuit:{source_name}` | None (managed by circuit breaker) | State machine transitions |
| Rate limit counters | `rate_limit:{ip}:{group}:{window}` | Window duration | Time-based expiry |

**Query Normalization for Cache Keys**

Before hashing, the query is normalized:

1. Convert to lowercase.
2. Remove leading/trailing whitespace.
3. Collapse multiple spaces to single space.
4. Sort filter parameters alphabetically.
5. Compute SHA-256 hash of the normalized string.

This ensures that "Noise Cancelling Headphones" and "noise cancelling headphones" hit the same cache entry.

**Cache-Aside Pattern**

```
Request arrives for a search query
    |
    v
Compute query_hash from normalized query
    |
    v
Check Redis: GET cache:search:{query_hash}
    |
    +---> Hit: return cached results immediately (HTTP 200, no WebSocket needed)
    +---> Miss: create new search job (proceed with full pipeline)
```

When a search completes, the worker writes results to the cache. The Backend API checks the cache before enqueuing a new job.

### 6.4 Queue-Based Processing for Concurrent Searches

**Problem**

Without queuing, N simultaneous search requests would cause N * M external API calls (where M is the number of sources), potentially overwhelming external rate limits and worker resources.

**Solution**

The Redis list (`queue:searches`) acts as a buffer. Workers pull jobs at their own pace.

**Backpressure Handling**

1. If the queue depth exceeds a configurable maximum (default: 100), the Backend API returns HTTP 503 with a `Retry-After` header instead of enqueuing.
2. Workers process one job at a time but use async I/O to make concurrent external API calls within a single job.
3. Each worker has a configurable concurrency limit (`WORKER_CONCURRENCY`, default 5) for simultaneous external requests per job.

---

## 7. Error Handling Strategy

### 7.1 Graceful Degradation

The system is designed to return the best possible results even when parts of it fail.

**Source Unavailability**

When a source fails (timeout, error, or circuit open), the search continues with remaining sources.

```
Sources configured:    [Amazon, BestBuy, PriceGrabber, AI Search]
Sources responding:    [Amazon, AI Search]
Sources failed:        [BestBuy (timeout), PriceGrabber (circuit open)]

Result: User receives results from Amazon and AI Search.
        UI displays notice: "2 of 4 sources were unavailable."
```

The search is only marked as `failed` if all sources fail.

**Degradation Tiers**

| Tier | Condition | Behavior |
|---|---|---|
| Full | All sources healthy | Complete results with AI ranking |
| Partial | Some sources failed | Results from available sources; failed sources noted in response |
| Minimal | All sources failed but cache available | Return stale cached results with "results may be outdated" warning |
| Failed | All sources failed, no cache | Return empty result set with error explanation |

### 7.2 Partial Results Handling

The WebSocket connection enables progressive delivery of results.

**Timeline of a Typical Search**

```
T+0.0s   Search started
T+0.5s   Source A returns 8 products       -> streamed to client
T+1.2s   Source B returns 12 products      -> streamed to client
T+3.0s   Source C times out                -> error event streamed to client
T+3.5s   AI ranking applied to 20 products -> final ranked list streamed
T+3.6s   Search marked complete
```

The frontend renders products as they arrive. Each partial result includes the `source` field so the UI can group or annotate results by origin.

**Partial Result Persistence**

Even if a search does not complete successfully, whatever results were gathered are persisted to PostgreSQL. The `searches.status` field distinguishes between `completed` (all sources responded) and `partial` (some sources failed). The user can always retrieve whatever was found.

### 7.3 User Notification for Failed Sources

**WebSocket Error Events**

When a source fails, the worker publishes an error event:

```json
{
  "event_type": "search.source_error",
  "search_id": "abc-123",
  "payload": {
    "source": "bestbuy",
    "error_code": "SOURCE_TIMEOUT",
    "message": "BestBuy did not respond within 10 seconds",
    "recoverable": false
  }
}
```

**Error Codes**

| Code | Meaning | User-Facing Message |
|---|---|---|
| `SOURCE_TIMEOUT` | External API did not respond in time | "[Source] is taking too long to respond" |
| `SOURCE_RATE_LIMITED` | External API returned 429 | "[Source] is temporarily limiting requests" |
| `SOURCE_UNAVAILABLE` | Circuit breaker is open | "[Source] is temporarily unavailable" |
| `SOURCE_ERROR` | External API returned 5xx | "[Source] encountered an error" |
| `PARSE_ERROR` | Response could not be parsed | "Could not read results from [Source]" |
| `AI_ERROR` | AI provider failed | "AI ranking unavailable; showing unranked results" |

**Final Search Response**

The completed search response (via REST) includes a `source_status` array:

```json
{
  "search_id": "abc-123",
  "status": "partial",
  "source_status": [
    { "source": "amazon", "status": "success", "result_count": 8 },
    { "source": "bestbuy", "status": "failed", "error_code": "SOURCE_TIMEOUT" },
    { "source": "ai_search", "status": "success", "result_count": 12 }
  ],
  "results": [ ... ],
  "total_results": 20
}
```

---

## 8. Data Architecture

### 8.1 Data Ownership

| Data | Owner | Storage | Accessed By |
|---|---|---|---|
| Search queries and history | Backend API | PostgreSQL | Backend API (read/write) |
| Search results | Backend API | PostgreSQL + Redis cache | Backend API (read/write), Search Worker (write to Redis only) |
| Real-time events | Search Worker | Redis Pub/Sub (ephemeral) | WebSocket Server (read) |
| Circuit breaker state | Search Worker | Redis | Search Workers (read/write), Backend API (read for monitoring) |
| Rate limit counters | Backend API | Redis | Backend API (read/write) |

### 8.2 Data Retention

| Data | Retention | Mechanism |
|---|---|---|
| Search results in PostgreSQL | 90 days | Scheduled deletion job (cron in Backend API) |
| Cached results in Redis | 1 hour | TTL-based expiry |
| Rate limit counters | 1 minute | TTL-based expiry |
| Real-time events | Ephemeral | Pub/Sub (not persisted) |
| Dead letter queue | 7 days | Manual review, then purge |

### 8.3 Consistency Model

The system uses eventual consistency between Redis and PostgreSQL.

- **During a search**: results exist only in Redis (cache + pub/sub). The source of truth is the worker's in-memory state.
- **After completion**: results are persisted to PostgreSQL via the `queue:persist` mechanism. PostgreSQL becomes the source of truth.
- **Window of inconsistency**: between search completion and persistence (typically under 1 second). During this window, the REST endpoint may return stale data, but the WebSocket connection has already delivered the final results.

This trade-off is acceptable because real-time delivery (via WebSocket) is the primary consumption path; the REST endpoint is for historical retrieval where a sub-second delay is imperceptible.

---

## 9. Docker Compose Architecture

### 9.1 Service Definitions and Dependencies

```
Service             Depends On              Startup Order
-------             ----------              -------------
postgres            (none)                  1st
redis               (none)                  1st (parallel with postgres)
backend-api         postgres, redis         2nd (after both are healthy)
search-worker       redis                   2nd (after redis is healthy)
websocket-server    redis                   2nd (after redis is healthy)
frontend            backend-api, ws-server  3rd (after API and WS are healthy)
```

**Dependency Type**: All dependencies use `condition: service_healthy` to ensure the depended-upon service is not merely started but actually ready to accept connections.

### 9.2 Network Configuration

```
Networks:
  shopping-net:
    driver: bridge

All services attach to shopping-net.
No service exposes ports to the host except frontend (Nginx).
```

**Service Discovery**

Services reference each other by Docker Compose service name. DNS resolution is automatic within the bridge network.

- Backend API connects to `postgres:5432` and `redis:6379`.
- Search Workers connect to `redis:6379`.
- WebSocket Server connects to `redis:6379`.
- Nginx proxies to `backend-api:8000` and `websocket-server:8001`.

### 9.3 Volume Management

| Volume | Type | Mounted In | Purpose |
|---|---|---|---|
| `postgres-data` | Named volume | postgres:/var/lib/postgresql/data | Persist database across container restarts |
| `redis-data` | Named volume | redis:/data | Persist Redis RDB snapshots (optional but recommended) |

**No Bind Mounts in Production**

Source code is baked into images at build time. Bind mounts are used only in development (for hot-reloading the frontend and backend).

**Development Overrides**

A `docker-compose.override.yml` file adds:

- Bind mounts for source code directories.
- Exposed ports for direct access to PostgreSQL (5432) and Redis (6379) for debugging.
- Volume mount for frontend node_modules to avoid platform-specific binary issues.

### 9.4 Health Checks

Every service defines a health check so that Docker (and dependent services) can determine readiness.

| Service | Health Check Command | Interval | Timeout | Retries |
|---|---|---|---|---|
| postgres | `pg_isready -U postgres` | 5s | 5s | 5 |
| redis | `redis-cli ping` | 5s | 5s | 5 |
| backend-api | `curl -f http://localhost:8000/api/v1/health` | 10s | 5s | 3 |
| websocket-server | `curl -f http://localhost:8001/health` | 10s | 5s | 3 |
| search-worker | Custom script: verify Redis connection and queue subscription | 10s | 5s | 3 |
| frontend (Nginx) | `curl -f http://localhost:80/` | 10s | 5s | 3 |

**Backend API Health Endpoint Response**

```json
{
  "status": "healthy",
  "checks": {
    "database": "connected",
    "redis": "connected",
    "queue_depth": 3
  },
  "version": "1.0.0",
  "uptime_seconds": 3600
}
```

### 9.5 Resource Limits

For predictable behavior on a single host, resource limits should be defined.

| Service | CPU Limit | Memory Limit | Rationale |
|---|---|---|---|
| postgres | 1.0 | 512 MB | Bounded query complexity |
| redis | 0.5 | 256 MB | Mostly small key-value operations |
| backend-api | 1.0 | 512 MB | Handles connection pools and request parsing |
| search-worker (per replica) | 1.0 | 512 MB | CPU-bound during AI processing |
| websocket-server | 0.5 | 256 MB | I/O-bound, low CPU |
| frontend (Nginx) | 0.25 | 128 MB | Serves static files |

---

## 10. Observability and Health

### 10.1 Structured Logging

All Python services emit JSON-structured logs to stdout (captured by Docker).

**Log Fields**

```json
{
  "timestamp": "2026-03-15T12:00:00.000Z",
  "level": "INFO",
  "service": "search-worker",
  "worker_id": "worker-02",
  "search_id": "abc-123",
  "source": "amazon",
  "message": "Source returned 8 results in 1.2s",
  "duration_ms": 1200,
  "result_count": 8
}
```

**Correlation**

The `search_id` field is present in every log line related to a search, across all services. This enables tracing a single search request from the Backend API through the queue, into the worker, and out through the WebSocket Server.

### 10.2 Key Metrics to Monitor

| Metric | Source | Alert Threshold |
|---|---|---|
| Queue depth | Redis `LLEN queue:searches` | > 20 sustained for 60s |
| Search latency (p95) | Backend API logs | > 10 seconds |
| External source error rate | Search Worker logs | > 50% for any source in 5 minutes |
| WebSocket active connections | WebSocket Server | > 500 (resource planning) |
| Database connection pool usage | Backend API | > 80% of pool_size + max_overflow |
| Dead letter queue depth | Redis `LLEN queue:dead_letter` | > 0 |
| Redis memory usage | Redis INFO | > 80% of memory limit |

### 10.3 Liveness vs. Readiness

The Backend API health endpoint supports two modes:

- **Liveness** (`GET /api/v1/health`): returns 200 if the process is running. Used by Docker health checks.
- **Readiness** (`GET /api/v1/health?ready=true`): returns 200 only if PostgreSQL and Redis are both reachable. Used by load balancers to determine if the instance should receive traffic.

---

## 11. Architectural Decision Records

### ADR-001: Redis as Unified Queue, Cache, and Pub/Sub

**Context**: The system needs a task queue, a pub/sub broker, and a cache. Using three separate systems (RabbitMQ + Redis + Memcached) would add operational complexity.

**Decision**: Use Redis for all three roles.

**Consequences**: Simpler operations and fewer containers. Redis Pub/Sub is fire-and-forget (no message persistence), which is acceptable because search events are ephemeral. If durability of queue messages becomes critical, migrating the task queue to a dedicated broker (RabbitMQ, Amazon SQS) is straightforward because the queue interface is abstracted behind a thin wrapper.

---

### ADR-002: Separate WebSocket Server

**Context**: FastAPI natively supports WebSocket endpoints. Embedding them in the Backend API would be simpler to deploy.

**Decision**: Run WebSocket handling as a separate service.

**Consequences**: Independent scaling of REST and WebSocket workloads. Slightly more complex deployment (one additional container). The trade-off favors operational flexibility: WebSocket connections are long-lived and resource patterns differ fundamentally from short-lived REST requests.

---

### ADR-003: PostgreSQL as Single Relational Store

**Context**: Search results are semi-structured (variable metadata per source). A document database (MongoDB) was considered.

**Decision**: Use PostgreSQL with JSONB columns for variable fields.

**Consequences**: PostgreSQL's JSONB support provides flexible schema for metadata while retaining relational integrity for core fields (prices, ratings, foreign keys). The team operates one database technology instead of two. GIN indexes on JSONB columns provide adequate query performance for the expected data volume.

---

### ADR-004: Async Persistence via Persist Queue

**Context**: Search Workers could write directly to PostgreSQL, but this would require database credentials in workers and create a second database client.

**Decision**: Workers publish results to a Redis persist queue. The Backend API consumes this queue and writes to PostgreSQL.

**Consequences**: Only the Backend API holds database credentials, enforcing a single point of data access. Workers remain stateless and focused on external API interaction. The persist queue introduces a brief delay (sub-second) between result availability and database persistence, which is acceptable given that real-time delivery happens via WebSocket.

---

### ADR-005: Nginx as Production Reverse Proxy

**Context**: The frontend, API, and WebSocket Server need to be accessible from the browser. Exposing each service on a separate port creates CORS complexity and exposes internal services.

**Decision**: Use Nginx as the single entry point, reverse-proxying to internal services based on URL path.

**Consequences**: Single-origin architecture eliminates CORS. Only one port is exposed to the host. Nginx handles TLS termination (when certificates are added), static file serving, and request routing. The Frontend container in production is simply Nginx with baked-in static assets and a proxy configuration.

---

*This document should be treated as a living artifact. As the system evolves, update the relevant sections and add new ADRs for significant architectural decisions.*
