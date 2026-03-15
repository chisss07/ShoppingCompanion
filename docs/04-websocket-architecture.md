# WebSocket Architecture — AI-Powered Shopping Companion

**Document version:** 1.0
**Date:** 2026-03-15
**Scope:** Real-time communication layer covering search progress, price updates, and search completion notifications.

---

## Table of Contents

1. System Overview
2. Connection Management
3. Room and Channel Strategy
4. Event Definitions and Payload Schemas
5. Heartbeat and Connection Health
6. Backend Integration via Redis Pub/Sub
7. Client-Side Strategy
8. Scaling Considerations
9. Error Handling and Reliability
10. Operational Metrics and Monitoring

---

## 1. System Overview

The Shopping Companion real-time layer connects three tiers: browser clients, WebSocket gateway servers, and backend search workers. Each search is an independent asynchronous job. Workers fan out to multiple price sources in parallel and publish incremental progress as they receive results. The WebSocket gateway translates those worker-published events into per-client socket emissions.

### Component Map

```
Browser Client
    |
    | WebSocket (Socket.IO)
    |
WebSocket Gateway (Node.js cluster, N instances)
    |                        |
    | Redis Adapter          | Redis Pub/Sub
    |                        |
Redis (Pub/Sub + Session)   Search Worker Pool
                                    |
                        [Source A] [Source B] [Source C] ...
```

### Technology Choices

| Concern | Choice | Rationale |
|---|---|---|
| WebSocket library | Socket.IO v4 | Built-in rooms, reconnection, and adapter ecosystem |
| Multi-instance coordination | `@socket.io/redis-adapter` | Transparent cross-instance event broadcasting |
| Worker-to-gateway messaging | Redis Pub/Sub | Decoupled, fire-and-forget, low operational overhead |
| Session store | Redis | Shared across gateway instances for sticky-session-free operation |
| Transport fallback | HTTP long-polling | Socket.IO default; covers environments that block WebSocket upgrades |

---

## 2. Connection Management

### 2.1 Connection Lifecycle

A client connection passes through four states: `DISCONNECTED`, `CONNECTING`, `CONNECTED`, and `RECONNECTING`. The gateway manages the transition between each state.

```
DISCONNECTED
    |
    | Client calls connect()
    v
CONNECTING
    |
    | Handshake + auth middleware
    |
    |-- failure --> DISCONNECTED (error emitted to client)
    |
    | success
    v
CONNECTED
    |
    | Network loss / server restart
    v
RECONNECTING
    |
    | Backoff exhausted --> DISCONNECTED (terminal)
    | Backoff succeeds  --> CONNECTED (state reconciliation triggered)
```

### 2.2 Handshake and Authentication

Every connection request must carry a short-lived JWT in the Socket.IO handshake auth payload. The gateway validates the token in middleware before any room join or event subscription is permitted. An expired or missing token causes an immediate `connect_error` with reason `auth_failed`.

The JWT encodes the following claims:

| Claim | Type | Description |
|---|---|---|
| `sub` | string | User ID (anonymous session ID for unauthenticated users) |
| `session_id` | string | Shopping session identifier |
| `iat` | number | Issued-at timestamp (Unix seconds) |
| `exp` | number | Expiry timestamp; recommended TTL is 3 600 seconds |

### 2.3 Disconnect Handling

When a client disconnects, the gateway:

1. Marks the socket as `offline` in the Redis session store with a TTL of 300 seconds.
2. Retains the search-room membership record for the same 300-second window.
3. Continues buffering events destined for that socket in a per-socket Redis list (see Section 7.2).
4. On reconnect within the TTL window, replays the buffered list in order and removes it.
5. On TTL expiry, discards the buffer and removes the room membership.

---

## 3. Room and Channel Strategy

### 3.1 Search Session Rooms

Every search is assigned a globally unique `search_id` (UUIDv4) when it is created. A dedicated Socket.IO room is created for that search:

```
room name: search:{search_id}
```

A client joins this room immediately after the search is initiated. Only the socket belonging to the user who owns the search is admitted to the room. This enforces isolation: one client's search progress cannot leak to another client.

### 3.2 User Presence Room

Each authenticated user has a persistent presence room:

```
room name: user:{user_id}
```

This room is used for cross-device notifications (e.g., a search started on mobile completing and notifying a desktop session). All sockets belonging to the same user join this room on connect.

### 3.3 Room Membership Rules

| Room | Who joins | When they join | When they leave |
|---|---|---|---|
| `search:{search_id}` | Owning socket only | On `search:started` | On `search:complete`, `search:error`, or 5-minute TTL |
| `user:{user_id}` | All sockets for that user | On authenticated connect | On socket disconnect |

### 3.4 Redis Channel Naming Convention

Search workers publish to Redis channels that mirror the room names:

```
redis channel: ws:search:{search_id}
redis channel: ws:user:{user_id}
```

The `ws:` prefix namespaces WebSocket-destined messages away from other Redis usage in the system.

---

## 4. Event Definitions and Payload Schemas

All events flow server-to-client unless marked as bidirectional. All timestamps are ISO 8601 strings in UTC. All numeric IDs are strings to avoid JavaScript integer precision loss.

### 4.1 Base Envelope

Every event payload wraps domain data in a common envelope:

```json
{
  "event": "<event_name>",
  "search_id": "<uuid-v4>",
  "timestamp": "<ISO-8601-UTC>",
  "sequence": 14,
  "data": {}
}
```

| Field | Type | Description |
|---|---|---|
| `event` | string | Mirrors the Socket.IO event name; included for logging convenience |
| `search_id` | string | UUIDv4 identifying the search session |
| `timestamp` | string | Server-side emission time |
| `sequence` | integer | Monotonically increasing counter per `search_id`; starts at 1; used by the client to detect gaps during reconciliation |
| `data` | object | Event-specific payload described below |

---

### 4.2 `search:started`

Emitted when the search job is accepted and workers are about to fan out to sources.

**Direction:** Server to Client | **Room:** `search:{search_id}`

```json
{
  "event": "search:started",
  "search_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "timestamp": "2026-03-15T14:00:00.000Z",
  "sequence": 1,
  "data": {
    "query": "Sony WH-1000XM6 headphones",
    "normalized_query": "Sony WH-1000XM6",
    "sources_total": 8,
    "sources": [
      "amazon", "bestbuy", "walmart", "target",
      "bhphotovideo", "adorama", "costco", "ebay"
    ],
    "estimated_duration_ms": 4500,
    "user_id": "usr_0987654321",
    "session_id": "sess_1122334455"
  }
}
```

| Field | Type | Description |
|---|---|---|
| `query` | string | Raw user query |
| `normalized_query` | string | Query after AI normalization and disambiguation |
| `sources_total` | integer | Number of sources that will be queried |
| `sources` | string[] | Ordered list of source identifiers |
| `estimated_duration_ms` | integer | AI-estimated total search duration |

---

### 4.3 `search:source_checking`

Emitted when a worker begins querying a specific source. Multiple instances may be in flight simultaneously for parallel source queries.

**Direction:** Server to Client | **Room:** `search:{search_id}`

```json
{
  "event": "search:source_checking",
  "search_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "timestamp": "2026-03-15T14:00:00.320Z",
  "sequence": 2,
  "data": {
    "source_id": "amazon",
    "source_display_name": "Amazon",
    "source_logo_url": "https://cdn.shoppingcompanion.app/logos/amazon.svg",
    "worker_id": "worker-node-03",
    "attempt": 1
  }
}
```

`attempt` greater than 1 indicates a retry.

---

### 4.4 `search:source_complete`

Emitted when a worker finishes querying one source, regardless of whether results were found.

**Direction:** Server to Client | **Room:** `search:{search_id}`

```json
{
  "event": "search:source_complete",
  "search_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "timestamp": "2026-03-15T14:00:01.180Z",
  "sequence": 5,
  "data": {
    "source_id": "amazon",
    "source_display_name": "Amazon",
    "status": "success",
    "duration_ms": 860,
    "results_count": 3,
    "results": [
      {
        "listing_id": "lst_aaaa1111",
        "title": "Sony WH-1000XM6 Wireless Noise Canceling Headphones - Black",
        "price": { "amount": 349.99, "currency": "USD", "formatted": "$349.99" },
        "original_price": { "amount": 399.99, "currency": "USD", "formatted": "$399.99" },
        "discount_percent": 12.5,
        "in_stock": true,
        "stock_level": "high",
        "condition": "new",
        "seller": "Amazon.com",
        "seller_rating": 4.8,
        "shipping": { "free": true, "estimated_days": 2, "prime_eligible": true },
        "url": "https://www.amazon.com/dp/B0EXAMPLE",
        "image_url": "https://m.media-amazon.com/images/EXAMPLE.jpg",
        "rating": { "score": 4.6, "review_count": 12480 },
        "badges": ["amazon_choice", "prime"]
      }
    ],
    "lowest_price": { "amount": 329.99, "currency": "USD", "formatted": "$329.99" }
  }
}
```

`status` values:

| Value | Meaning |
|---|---|
| `success` | Source returned usable results |
| `no_results` | Source was reachable but returned zero matches |
| `error` | Source query failed (see `search:error` for detail) |
| `timeout` | Source did not respond within the timeout window |
| `rate_limited` | Source returned a rate-limit response |

When `status` is anything other than `success`, the `results` array is empty and `results_count` is 0.

---

### 4.5 `search:comparison_ready`

Emitted once all sources have responded (or timed out) and the AI comparison engine has produced a ranked summary.

**Direction:** Server to Client | **Room:** `search:{search_id}`

```json
{
  "event": "search:comparison_ready",
  "search_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "timestamp": "2026-03-15T14:00:04.750Z",
  "sequence": 18,
  "data": {
    "sources_succeeded": 7,
    "sources_failed": 1,
    "sources_timed_out": 0,
    "total_listings_found": 24,
    "best_deal": {
      "listing_id": "lst_bbbb2222",
      "source_id": "bestbuy",
      "price": { "amount": 319.99, "currency": "USD", "formatted": "$319.99" },
      "reason": "Lowest price among in-stock new units with free shipping"
    },
    "price_range": {
      "min": { "amount": 319.99, "currency": "USD", "formatted": "$319.99" },
      "max": { "amount": 389.00, "currency": "USD", "formatted": "$389.00" },
      "median": { "amount": 349.99, "currency": "USD", "formatted": "$349.99" }
    },
    "ai_summary": "The Sony WH-1000XM6 is currently available from 7 of 8 queried retailers. Best Buy offers the lowest new price at $319.99 with free standard shipping. Amazon Prime members can receive it in 2 days at $349.99. Avoid the eBay listings; all are used or third-party and priced above the retail range.",
    "ranked_listings": [
      { "rank": 1, "listing_id": "lst_bbbb2222", "source_id": "bestbuy", "score": 0.94 },
      { "rank": 2, "listing_id": "lst_aaaa1111", "source_id": "amazon", "score": 0.87 }
    ]
  }
}
```

---

### 4.6 `search:alternatives_found`

Emitted when the AI engine identifies alternative models that may satisfy the user's intent. This event may arrive before or after `search:comparison_ready`.

**Direction:** Server to Client | **Room:** `search:{search_id}`

```json
{
  "event": "search:alternatives_found",
  "search_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "timestamp": "2026-03-15T14:00:03.100Z",
  "sequence": 15,
  "data": {
    "alternatives": [
      {
        "alternative_id": "alt_0001",
        "product_name": "Sony WH-1000XM5",
        "reason": "Previous generation; 22% cheaper on average with comparable noise cancellation",
        "avg_price": { "amount": 278.00, "currency": "USD", "formatted": "$278.00" },
        "confidence": 0.88,
        "search_id_for_alternative": null
      },
      {
        "alternative_id": "alt_0002",
        "product_name": "Bose QuietComfort 45",
        "reason": "Competing flagship; similar price bracket with stronger call quality reviews",
        "avg_price": { "amount": 329.00, "currency": "USD", "formatted": "$329.00" },
        "confidence": 0.76,
        "search_id_for_alternative": null
      }
    ],
    "ai_rationale": "Based on your query, you may be primarily interested in premium noise-canceling headphones. These alternatives have been identified based on price-performance analysis across the same sources."
  }
}
```

`search_id_for_alternative` is `null` on first emission. If the user requests an alternative be searched, a new search is started and this field is populated with the new `search_id`, linking the two searches.

---

### 4.7 `search:complete`

Emitted when all processing for the search is finished. This is the terminal success event for the search room.

**Direction:** Server to Client | **Room:** `search:{search_id}`

```json
{
  "event": "search:complete",
  "search_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "timestamp": "2026-03-15T14:00:05.010Z",
  "sequence": 20,
  "data": {
    "total_duration_ms": 5010,
    "sources_queried": 8,
    "sources_succeeded": 7,
    "total_listings_found": 24,
    "result_url": "/results/a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "cache_ttl_seconds": 300,
    "next_refresh_available_at": "2026-03-15T14:05:05.000Z"
  }
}
```

After this event is received, the client should leave `search:{search_id}`. The gateway removes the room after the `cache_ttl_seconds` window. `result_url` is a REST endpoint the client can poll for updated results after a background re-check runs.

---

### 4.8 `search:error`

Emitted when an error occurs on a specific source. Non-terminal by default; the search continues against other sources.

**Direction:** Server to Client | **Room:** `search:{search_id}`

```json
{
  "event": "search:error",
  "search_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "timestamp": "2026-03-15T14:00:01.900Z",
  "sequence": 7,
  "data": {
    "source_id": "ebay",
    "source_display_name": "eBay",
    "error_code": "SOURCE_TIMEOUT",
    "error_message": "eBay search API did not respond within the 3 000 ms window.",
    "retryable": true,
    "retry_attempt": 1,
    "max_retries": 2,
    "fatal": false
  }
}
```

When `fatal` is `true`, the entire search has failed. `search:complete` will not be emitted and the client must treat the search as definitively failed.

`error_code` values:

| Code | Meaning |
|---|---|
| `SOURCE_TIMEOUT` | Individual source exceeded response timeout |
| `SOURCE_RATE_LIMITED` | Source returned HTTP 429 |
| `SOURCE_UNAVAILABLE` | Source returned 5xx or connection refused |
| `SOURCE_PARSE_FAILURE` | Source returned unparseable response |
| `SEARCH_QUEUE_FULL` | Job queue rejected the search (fatal) |
| `SEARCH_INVALID_QUERY` | Query could not be processed (fatal) |
| `SEARCH_INTERNAL_ERROR` | Unexpected worker error (fatal) |

---

### 4.9 `search:progress`

Emitted at regular intervals (maximum once per 500 ms) to provide overall percentage completion. Multiple rapid state changes within a 500 ms window are coalesced into a single emission.

**Direction:** Server to Client | **Room:** `search:{search_id}`

```json
{
  "event": "search:progress",
  "search_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "timestamp": "2026-03-15T14:00:02.500Z",
  "sequence": 10,
  "data": {
    "percent_complete": 62,
    "sources_complete": 5,
    "sources_total": 8,
    "sources_in_progress": ["walmart", "target", "costco"],
    "sources_pending": [],
    "sources_done": [
      { "source_id": "amazon", "status": "success" },
      { "source_id": "bestbuy", "status": "success" },
      { "source_id": "bhphotovideo", "status": "success" },
      { "source_id": "adorama", "status": "success" },
      { "source_id": "ebay", "status": "timeout" }
    ],
    "elapsed_ms": 2500,
    "estimated_remaining_ms": 1800
  }
}
```

---

### 4.10 Client-to-Server Events

#### `search:subscribe`

Join a search room after the search has already started (e.g., user opens a deep link to an in-progress search). The server responds with an acknowledgement:

```json
{
  "status": "joined",
  "search_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "current_state": {
    "percent_complete": 50,
    "sources_done": ["..."],
    "sources_in_progress": ["..."],
    "sequence_latest": 9
  },
  "missed_events": [
    { "sequence": 1, "event": "search:started", "data": {} },
    "..."
  ]
}
```

`missed_events` contains all events from sequence 1 to `sequence_latest` in order, enabling a late-joining client to reconstruct full state.

#### `search:unsubscribe`

Leave a search room explicitly. Payload: `{ "search_id": "<uuid>" }`.

---

## 5. Heartbeat and Connection Health

### 5.1 Transport-Level Ping/Pong

Socket.IO's built-in Engine.IO ping/pong handles baseline connection health.

| Parameter | Value |
|---|---|
| `pingInterval` | 25 000 ms |
| `pingTimeout` | 20 000 ms |
| `upgradeTimeout` | 10 000 ms |
| `maxHttpBufferSize` | 1 MB |

### 5.2 Application-Level Heartbeat

The gateway emits a `gateway:heartbeat` every 30 seconds to any socket in an active search room. This verifies the event pipeline, not just the TCP connection, is alive.

```json
{
  "event": "gateway:heartbeat",
  "timestamp": "2026-03-15T14:00:30.000Z",
  "server_instance": "ws-gateway-pod-07",
  "active_search_ids": ["a1b2c3d4-e5f6-7890-abcd-ef1234567890"]
}
```

The client responds with `gateway:heartbeat_ack`. If no ack arrives within 10 seconds, the gateway logs the socket as potentially degraded but does not forcibly disconnect it — the transport-level ping/pong handles disconnection.

### 5.3 Dead Connection Detection

If the transport-level ping/pong fails and the application-level heartbeat receives no ack for two consecutive cycles, the gateway marks the socket record in Redis as `stale`. Stale sockets that reconnect within the 300-second buffer TTL receive their queued events. Stale sockets that do not reconnect within that window are cleaned up.

---

## 6. Backend Integration via Redis Pub/Sub

### 6.1 Architecture Overview

Search workers and the WebSocket gateway are decoupled by Redis Pub/Sub. Workers never hold a reference to a socket; they only know the `search_id` and publish to the corresponding Redis channel. The gateway subscribes to channels for active searches and forwards messages to the appropriate Socket.IO room.

```
Search Worker
    |
    | PUBLISH ws:search:{search_id}  <serialized event envelope>
    v
Redis Pub/Sub
    |
    | Message delivered to all subscribers
    v
WebSocket Gateway Instance(s)
    |
    | io.to('search:{search_id}').emit(event, payload)
    v
Browser Client in room search:{search_id}
```

### 6.2 Worker Publishing Contract

Workers publish JSON-serialized event envelopes to `ws:search:{search_id}`. The envelope format is identical to the client-facing payload in Section 4.1.

Workers are responsible for:

- Assigning a `sequence` number via a Redis INCR on key `seq:{search_id}`. This guarantees globally ordered sequence numbers even when multiple workers handle the same search in parallel.
- Setting a correct `timestamp` in UTC ISO 8601.
- Publishing the event before performing any cleanup or state transitions.

Workers are not responsible for knowing which gateway instance or socket is handling a given client. Redis Pub/Sub and the Socket.IO adapter handle routing.

### 6.3 Gateway Subscription Management

The gateway subscribes to a Redis channel when a client joins a search room, and unsubscribes when the last client leaves or the room TTL expires.

| Trigger | Gateway action |
|---|---|
| First socket joins `search:{search_id}` | `SUBSCRIBE ws:search:{search_id}` |
| Event received on channel | Emit to Socket.IO room, append to event buffer |
| `search:complete` or fatal `search:error` received | Schedule unsubscription after 300-second buffer TTL |
| Last socket leaves and TTL has passed | `UNSUBSCRIBE`, delete event buffer |

### 6.4 Event Buffer in Redis

Every event published to `ws:search:{search_id}` is appended by the gateway to a Redis list:

| Property | Value |
|---|---|
| Key | `evtbuf:{search_id}` |
| Type | Redis List (RPUSH / LRANGE) |
| TTL | 300 seconds, reset on each RPUSH |
| Maximum entries | 500 (LTRIM removes oldest beyond this) |

This buffer serves two purposes: late-joining clients receive full event history via `search:subscribe` acknowledgement, and reconnecting clients receive only the events they missed (identified by their last acknowledged `sequence` number).

### 6.5 Cross-Instance Event Routing

The `@socket.io/redis-adapter` handles cross-instance room emission transparently. When the gateway receives a Redis Pub/Sub message, it calls `io.to('search:{search_id}').emit(...)`. The adapter ensures the emission reaches the correct socket regardless of which gateway instance it is connected to. Sticky sessions are not required for correctness; they are recommended only for reducing unnecessary cross-instance traffic.

---

## 7. Client-Side Strategy

### 7.1 Connection State Machine

```
IDLE
  |
  | User initiates search
  v
CONNECTING
  |
  | connect event
  v
CONNECTED
  |    |
  |    | Network loss
  |    v
  |    RECONNECTING
  |    |    |
  |    |    | Max retries reached
  |    |    v
  |    |    FAILED (terminal)
  |    |
  |    | Reconnect successful
  |    v
  |    CONNECTED (state reconciliation triggered)
  |
  | search:complete received
  v
IDLE
```

### 7.2 Auto-Reconnection with Exponential Backoff

The client uses exponential backoff with full jitter to avoid thundering-herd storms after a server restart.

| Parameter | Value |
|---|---|
| Initial delay | 1 000 ms |
| Multiplier | 2 |
| Maximum delay | 30 000 ms |
| Jitter | Full jitter (random value between 0 and computed delay) |
| Maximum attempts | 10 |

Delay formula: `actual_delay = random(0, min(initial_delay * 2^n, max_delay))`

Approximate schedule before jitter:

| Attempt | Base delay |
|---|---|
| 1 | 1 000 ms |
| 2 | 2 000 ms |
| 3 | 4 000 ms |
| 4 | 8 000 ms |
| 5 | 16 000 ms |
| 6-10 | 30 000 ms (capped) |

After 10 failed attempts the client transitions to `FAILED` and surfaces a manual "Retry connection" control rather than continuing to reconnect automatically.

Socket.IO configuration: `reconnection: true`, `reconnectionAttempts: 10`, `reconnectionDelay: 1000`, `reconnectionDelayMax: 30000`, `randomizationFactor: 1.0`.

### 7.3 Message Queuing During Disconnection

During disconnection, the client queues outbound messages (primarily `search:subscribe` requests) in an in-memory array bounded at 50 messages. On reconnection, the queue is flushed in order before any new messages are sent. Inbound message gaps are resolved by state reconciliation from the server-side event buffer, not client-side buffering.

### 7.4 State Reconciliation After Reconnect

1. The client tracks `last_known_sequence` — the highest sequence number it successfully processed before disconnecting.
2. On reconnect, the client re-emits `search:subscribe` for each active `search_id` it was tracking.
3. The gateway's acknowledgement includes `missed_events` containing all events with `sequence > last_known_sequence`.
4. The client applies missed events in sequence order, updating local state as if received in real time.
5. If `search:complete` appears in `missed_events`, the client transitions directly to the completed state and fetches full results from `search:complete.data.result_url`.
6. If `last_known_sequence` equals `sequence_latest`, no reconciliation is needed.

---

## 8. Scaling Considerations

### 8.1 Horizontal Gateway Scaling

Each gateway instance is stateless with respect to business logic. All shared state lives in Redis. Target sizing per instance:

| Resource | Recommendation |
|---|---|
| Concurrent connections | 10 000 per instance |
| CPU | 2 vCPU |
| Memory | 2 GB |
| Network | 1 Gbps |

Autoscaling should trigger at 70% of the per-instance connection limit.

### 8.2 Load Balancer Configuration

| Requirement | Detail |
|---|---|
| Protocol | TCP (not HTTP) to avoid proxy buffering on WebSocket frames |
| Health check | TCP check on gateway port; interval 10 s, unhealthy threshold 2 |
| Idle timeout | 3 600 s (must exceed `pingInterval + pingTimeout`) |
| Session affinity | IP hash preferred; cookie-based acceptable if client IPs are unstable |

### 8.3 Redis Configuration

| Concern | Configuration |
|---|---|
| Topology | Redis Cluster with 3 primary shards and 1 replica per shard |
| Persistence | RDB snapshots every 5 minutes; AOF disabled for Pub/Sub workloads |
| Eviction policy | `allkeys-lru` to prevent OOM on event buffer accumulation |
| Max memory | 80% of available RAM per node |
| Event buffer TTL | 300 s |
| Session record TTL | 300 s |
| Sequence counter TTL | 600 s |

### 8.4 Graceful Shutdown and Zero-Downtime Deployment

1. Instance stops accepting new connections (removed from load balancer target group).
2. Instance emits `gateway:draining` to all connected sockets with a `reconnect_in_ms` hint (typically 5 000 ms).
3. Client state machine transitions to `RECONNECTING`, triggering reconnection to a healthy instance.
4. Instance waits for all sockets to disconnect (or a maximum drain timeout of 30 seconds) before exiting.
5. Reconnecting clients reconcile missed events from the new instance using the Redis event buffer.

### 8.5 Connection Limits and Resource Management

| Limit | Value | Enforcement |
|---|---|---|
| Max concurrent searches per user | 5 | Rejected with `SEARCH_QUEUE_FULL` |
| Max message size (inbound) | 4 KB | Socket immediately closed on violation |
| Max subscriptions per socket | 10 rooms | 11th `search:subscribe` rejected |
| Inbound event rate limit | 10 events/second per socket | Excess events dropped; client warned |

---

## 9. Error Handling and Reliability

### 9.1 Source-Level Errors

Communicated via `search:error` with `fatal: false`. Workers retry according to their own policy (typically 2 retries with a 500 ms delay). After exhausting retries, the source is marked failed and counted in `sources_failed` in the final summary events.

### 9.2 Fatal Search Errors

Communicated via `search:error` with `fatal: true`. The client should display the `error_message`, offer a retry button that initiates a new search (new `search_id`), leave the failed search room, and clear the local event buffer for the failed `search_id`.

### 9.3 Gateway-Internal Errors

If the gateway encounters an internal error processing a Redis Pub/Sub message, it logs the error, increments the `ws_gateway_processing_errors_total` metric, and continues. It does not emit an error to the client, as the event remains available in the Redis event buffer for reconciliation.

### 9.4 Redis Connectivity Loss

1. Gateway continues serving existing socket connections from in-process state.
2. Gateway stops accepting new `search:subscribe` requests and returns an error to callers.
3. Gateway emits `gateway:degraded` to all connected sockets.
4. Gateway retries the Redis connection with exponential backoff.
5. On Redis reconnect, gateway re-subscribes to all active channels and resumes normal operation.

`gateway:degraded` payload:

```json
{
  "event": "gateway:degraded",
  "timestamp": "2026-03-15T14:01:00.000Z",
  "reason": "redis_unavailable",
  "message": "Real-time updates are temporarily unavailable. Your search is continuing and results will appear when connectivity is restored.",
  "estimated_recovery_ms": null
}
```

---

## 10. Operational Metrics and Monitoring

### 10.1 Key Metrics

| Metric name | Type | Description |
|---|---|---|
| `ws_connections_active` | Gauge | Current connected sockets per gateway instance |
| `ws_connections_total` | Counter | Total connections accepted since startup |
| `ws_disconnections_total` | Counter | Total disconnections, labelled by reason |
| `ws_reconnections_total` | Counter | Total successful reconnections |
| `ws_events_emitted_total` | Counter | Events emitted to clients, labelled by event name |
| `ws_events_received_total` | Counter | Events received from clients, labelled by event name |
| `ws_search_rooms_active` | Gauge | Active search rooms across all instances |
| `ws_event_buffer_size` | Histogram | Size of per-search event buffers in Redis |
| `ws_pubsub_lag_ms` | Histogram | Time between worker Redis PUBLISH and gateway socket emit |
| `ws_gateway_processing_errors_total` | Counter | Gateway-internal processing errors |
| `ws_redis_connectivity_loss_total` | Counter | Redis connectivity loss events |

### 10.2 Alerting Thresholds

| Alert | Condition | Severity |
|---|---|---|
| High connection count | `ws_connections_active` > 8 000 per instance | Warning |
| Connection saturation | `ws_connections_active` > 9 500 per instance | Critical |
| Pub/Sub lag warning | p99 `ws_pubsub_lag_ms` > 500 ms for 5 minutes | Warning |
| Pub/Sub lag critical | p99 `ws_pubsub_lag_ms` > 2 000 ms for 2 minutes | Critical |
| Redis connectivity | `ws_redis_connectivity_loss_total` increments | Critical |
| Processing errors | `ws_gateway_processing_errors_total` rate > 10/min | Warning |

### 10.3 Logging Standards

Every log entry produced by the gateway must include:

- `search_id` when associated with a specific search
- `socket_id` when associated with a specific connection
- `server_instance` identifier
- Structured JSON format for log aggregation compatibility

---

## Design Decisions Summary

To close with a short rationale record for future maintainers:

**Why Socket.IO over raw WebSocket?** The built-in room abstraction, Redis adapter, automatic transport fallback, and reconnection machinery eliminate significant boilerplate. The tradeoff is a slightly larger client bundle, which is acceptable for a web app.

**Why per-search rooms rather than per-user channels?** Isolation is the primary concern. A user running two simultaneous searches should receive independent event streams for each. Per-search rooms enforce this without any application-level filtering logic.

**Why Redis Pub/Sub for worker-to-gateway communication rather than a message queue?** Search progress events are ephemeral and time-sensitive. Delivery guarantees beyond the 300-second event buffer window are not required. Redis Pub/Sub's lower operational complexity and sub-millisecond delivery latency are the right tradeoffs here. A message queue (Kafka, RabbitMQ) would be appropriate if events needed to be durably replayed hours later, which is not a requirement for this system.

**Why sequence numbers rather than timestamps for gap detection?** Timestamps are susceptible to clock skew between worker nodes. An atomic INCR counter in Redis produces a gapless, monotonically increasing integer that is reliable regardless of which worker node produced the event.

**Why 10 reconnection attempts with a 30-second cap?** This gives the client approximately 4 minutes of retry coverage (sum of all backoff delays before jitter), which covers typical deployment rollover windows. Beyond 4 minutes, a search is almost certainly complete or failed, so surfacing a manual retry to the user is more appropriate than silent infinite reconnection.
