"""
Shopping Companion WebSocket Server
====================================

FastAPI application that bridges Redis pub/sub events (published by Celery
search workers) to browser clients over WebSocket.

Architecture summary
--------------------
- One uvicorn worker, one asyncio event loop, one in-process connection
  registry (ConnectionManager).
- A background asyncio Task (RedisEventListener) holds a single persistent
  PSUBSCRIBE connection to Redis and fans out every received message to all
  WebSocket connections in the matching search room.
- Late-joining clients replay buffered events from Redis (evtbuf:{search_id})
  immediately after the handshake, eliminating the need for the browser to
  poll.

Routes
------
GET  /health                     Health check for Docker/Compose/nginx probes.
WS   /ws/search/{search_id}      Real-time stream for a specific search session.
WS   /ws/user/{user_id}          Reserved for future per-user notifications.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import redis.asyncio as aioredis
import structlog
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from app.connection_manager import ConnectionManager
from app.core.config import get_settings
from app.redis_listener import RedisEventListener
from app.websocket_handler import handle_search_websocket, handle_user_websocket

# ── Structured logging must be configured before any logger is obtained ──────
# Import the same helper used by the backend so log format is consistent.
import logging
import sys


def _configure_logging(log_level: str, is_production: bool) -> None:
    """
    Minimal structlog configuration that mirrors the backend's setup.

    Using an inline function avoids a circular import while still letting us
    reuse the same pattern without duplicating it in a shared library.
    """
    import structlog as sl

    shared_processors = [
        sl.contextvars.merge_contextvars,
        sl.stdlib.add_log_level,
        sl.stdlib.PositionalArgumentsFormatter(),
        sl.processors.TimeStamper(fmt="iso"),
        sl.processors.StackInfoRenderer(),
    ]

    if is_production:
        processors = [
            *shared_processors,
            sl.processors.format_exc_info,
            sl.processors.JSONRenderer(),
        ]
    else:
        processors = [
            *shared_processors,
            sl.dev.ConsoleRenderer(colors=True),
        ]

    sl.configure(
        processors=processors,
        wrapper_class=sl.make_filtering_bound_logger(
            logging.getLevelName(log_level.upper())
        ),
        context_class=dict,
        logger_factory=sl.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.getLevelName(log_level.upper()),
    )
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


settings = get_settings()
_configure_logging(settings.LOG_LEVEL, settings.is_production)

logger = structlog.get_logger(__name__)


# ── Application state ────────────────────────────────────────────────────────

class AppState:
    """
    Container for shared application-level objects.

    Attached to ``app.state`` during lifespan so route handlers can access
    them via ``request.app.state`` without global variables.
    """

    manager: ConnectionManager
    redis: aioredis.Redis
    listener: RedisEventListener
    listener_task: asyncio.Task


# ── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Manage the lifecycle of shared resources.

    Startup:
        - Connect to Redis.
        - Create the ConnectionManager.
        - Create and start the RedisEventListener background task.

    Shutdown:
        - Stop the listener task gracefully.
        - Close the Redis connection.
    """
    state = AppState()

    # ── Startup ──────────────────────────────────────────────────────────────
    logger.info(
        "websocket_server_starting",
        redis_url=settings.REDIS_URL,
        log_level=settings.LOG_LEVEL,
        debug=settings.DEBUG,
    )

    # Shared async Redis client for regular commands (LRANGE, etc.)
    state.redis = aioredis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_keepalive=True,
    )

    # Verify connectivity early so the health check starts healthy.
    try:
        await state.redis.ping()
        logger.info("redis_connected", redis_url=settings.REDIS_URL)
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "redis_connection_failed",
            redis_url=settings.REDIS_URL,
            error=str(exc),
        )
        # Allow the server to start anyway; the listener will retry.

    state.manager = ConnectionManager()

    state.listener = RedisEventListener(
        redis_url=settings.REDIS_URL,
        manager=state.manager,
    )

    state.listener_task = asyncio.create_task(
        state.listener.start(),
        name="redis-event-listener",
    )

    # Attach state to the app so routes can access it.
    app.state.manager = state.manager
    app.state.redis = state.redis
    app.state.listener = state.listener

    logger.info("websocket_server_ready", port=8001)

    yield  # ── Server is running ─────────────────────────────────────────────

    # ── Shutdown ─────────────────────────────────────────────────────────────
    logger.info("websocket_server_shutting_down")

    await state.listener.stop()
    state.listener_task.cancel()
    try:
        await state.listener_task
    except (asyncio.CancelledError, Exception):
        pass

    await state.redis.aclose()
    logger.info("websocket_server_shutdown_complete")


# ── FastAPI application ───────────────────────────────────────────────────────

app = FastAPI(
    title="Shopping Companion WebSocket Server",
    description=(
        "Real-time bridge between Celery search workers (via Redis pub/sub) "
        "and browser clients over WebSocket."
    ),
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url=None,
    lifespan=lifespan,
)

# Allow the frontend origin to open WebSocket connections.
# In production, nginx handles CORS at the proxy layer, but the middleware is
# kept here as a defence-in-depth measure and for local development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tightened at the nginx layer in production
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["ops"])
async def health() -> dict:
    """
    Health probe endpoint consumed by Docker, Compose, and nginx upstreams.

    Returns the total number of active WebSocket connections so operators can
    monitor load without needing a separate metrics scrape.
    """
    manager: ConnectionManager = app.state.manager
    return {
        "status": "ok",
        "connections": manager.get_connection_count(),
        "rooms": manager.get_room_count(),
    }


@app.websocket("/ws/search/{search_id}")
async def websocket_search(websocket: WebSocket, search_id: str) -> None:
    """
    Real-time event stream for a search session.

    Path parameter
    --------------
    search_id : str
        The UUID (or other identifier) of the search session created via the
        backend REST API. Must match the search_id used by the worker when it
        publishes to ``ws:search:{search_id}``.

    Protocol
    --------
    Server -> Client messages (JSON):
        ``{"type": "buffered_events", "events": [...]}``
            Sent immediately after connection. Contains all events published
            before this client connected. May be omitted if the buffer is empty.

        ``{"type": "ping"}``
            Sent every 25 s. The client may respond with ``{"action": "pong"}``.

        Any event dict published by the worker is forwarded verbatim.

    Client -> Server messages (JSON):
        ``{"action": "cancel"}``
            Request to cancel the search. The server acknowledges with
            ``{"type": "cancel_acknowledged"}`` and the client should call
            DELETE /api/v1/searches/{search_id} to actually stop the worker.

        ``{"action": "pong"}``
            Optional reply to a server ping.
    """
    manager: ConnectionManager = app.state.manager
    redis_client: aioredis.Redis = app.state.redis

    logger.info("ws_search_route_invoked", search_id=search_id)

    await handle_search_websocket(
        websocket=websocket,
        search_id=search_id,
        manager=manager,
        redis_client=redis_client,
    )


@app.websocket("/ws/user/{user_id}")
async def websocket_user(websocket: WebSocket, user_id: str) -> None:
    """
    Per-user notification channel (reserved for future use).

    Intended for features such as price-drop alerts, saved-search completion
    notifications, and account-level events. Currently the server accepts the
    connection, sends a ``connected`` acknowledgement, and keeps it alive.

    Path parameter
    --------------
    user_id : str
        The authenticated user's identifier. Authentication/authorisation
        middleware will be added here when the feature is built out.
    """
    manager: ConnectionManager = app.state.manager
    redis_client: aioredis.Redis = app.state.redis

    logger.info("ws_user_route_invoked", user_id=user_id)

    await handle_user_websocket(
        websocket=websocket,
        user_id=user_id,
        manager=manager,
        redis_client=redis_client,
    )
