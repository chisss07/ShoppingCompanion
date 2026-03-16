"""
WebSocket request handlers.

Each handler coroutine is invoked by a FastAPI route and owns the full
lifetime of one WebSocket connection: handshake, history replay, keep-alive
pings, client message processing, and clean disconnect.

Event buffer
------------
When a worker publishes events while no browser has connected yet (common for
fast searches), or when a client disconnects and reconnects, the event buffer
stored in Redis (``evtbuf:{search_id}``) is sent immediately after the
handshake so the client receives the complete history without polling.

Keep-alive
----------
Browsers and intermediary proxies (nginx, load balancers) will close idle
WebSocket connections after their own timeout. A server-side ping every 25 s
keeps the connection alive and lets us detect half-open TCP sessions quickly.

Client messages
---------------
The only message the server currently acts on is ``{"action": "cancel"}``.
Future protocol extensions (pause, resume, ack) can be added here without
changing the route layer.
"""

from __future__ import annotations

import asyncio
import json

import redis.asyncio as aioredis
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect, WebSocketState

from app.connection_manager import ConnectionManager

import structlog

logger = structlog.get_logger(__name__)

# Interval between server-side pings (seconds).
_PING_INTERVAL = 25

# Redis key prefix for the per-search event buffer.
_EVTBUF_PREFIX = "evtbuf:"


async def handle_search_websocket(
    websocket: WebSocket,
    search_id: str,
    manager: ConnectionManager,
    redis_client: aioredis.Redis,
) -> None:
    """
    Handle a WebSocket connection scoped to a specific search.

    Lifecycle
    ---------
    1. Accept the WebSocket handshake.
    2. Replay buffered events from Redis so the client is up-to-date even
       if it connects after the search has already started.
    3. Register the connection with the ConnectionManager so it receives
       future broadcast events.
    4. Run two concurrent tasks:
       a. Keep-alive: sends a ping frame every _PING_INTERVAL seconds.
       b. Reader: receives messages from the client and acts on them.
    5. On disconnect (clean or error): unregister from ConnectionManager.

    Parameters
    ----------
    websocket:    The raw Starlette WebSocket, not yet accepted.
    search_id:    Identifier of the search session this socket is joining.
    manager:      Shared ConnectionManager instance injected from app state.
    redis_client: Async Redis client for reading the event buffer.
    """

    # ── 1. Accept connection ─────────────────────────────────────────────────
    # manager.connect() calls websocket.accept() internally.
    await manager.connect(search_id, websocket)

    try:
        # ── 2. Replay buffered events ────────────────────────────────────────
        await _replay_event_buffer(websocket, search_id, redis_client)

        # ── 3 & 4. Run keep-alive and reader concurrently ────────────────────
        ping_task = asyncio.create_task(
            _ping_loop(websocket, search_id),
            name=f"ping-{search_id}",
        )
        reader_task = asyncio.create_task(
            _message_reader(websocket, search_id),
            name=f"reader-{search_id}",
        )

        # Wait for either task to finish. The reader exits on disconnect;
        # the ping exits on send failure (also indicating disconnect).
        done, pending = await asyncio.wait(
            {ping_task, reader_task},
            return_when=asyncio.FIRST_COMPLETED,
        )

        # Cancel whichever task is still running.
        for task in pending:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

        # Propagate exceptions from finished tasks (for structured logging).
        for task in done:
            exc = task.exception()
            if exc is not None and not isinstance(exc, WebSocketDisconnect):
                logger.warning(
                    "ws_task_raised",
                    search_id=search_id,
                    task=task.get_name(),
                    error=str(exc),
                )

    except WebSocketDisconnect:
        logger.info("ws_client_disconnected_cleanly", search_id=search_id)
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "ws_handler_unexpected_error",
            search_id=search_id,
            error=str(exc),
            exc_info=True,
        )
    finally:
        # ── 5. Unregister connection ─────────────────────────────────────────
        await manager.disconnect(search_id, websocket)


async def handle_user_websocket(
    websocket: WebSocket,
    user_id: str,
    manager: ConnectionManager,
    redis_client: aioredis.Redis,
) -> None:
    """
    Placeholder handler for per-user notification connections.

    Reserved for future features such as price-drop alerts, saved-search
    notifications, and account-level events. The channel pattern for the
    Redis listener would be ``ws:user:{user_id}``.

    Parameters
    ----------
    websocket:    The raw Starlette WebSocket, not yet accepted.
    user_id:      Authenticated user identifier.
    manager:      Shared ConnectionManager instance injected from app state.
    redis_client: Async Redis client (unused until notifications are built).
    """
    await websocket.accept()
    logger.info("ws_user_connected", user_id=user_id)

    try:
        # Send an initial acknowledgement so the client knows the connection
        # is live even though no events are published yet.
        await websocket.send_json(
            {
                "type": "connected",
                "user_id": user_id,
                "message": "User notification channel connected. Feature coming soon.",
            }
        )

        # Keep the connection alive until the client disconnects or the server
        # shuts down.  Future work: subscribe to ws:user:{user_id} Redis channel.
        ping_task = asyncio.create_task(
            _ping_loop(websocket, f"user:{user_id}"),
            name=f"ping-user-{user_id}",
        )
        reader_task = asyncio.create_task(
            _message_reader(websocket, f"user:{user_id}"),
            name=f"reader-user-{user_id}",
        )

        done, pending = await asyncio.wait(
            {ping_task, reader_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

    except WebSocketDisconnect:
        logger.info("ws_user_disconnected", user_id=user_id)
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "ws_user_handler_error",
            user_id=user_id,
            error=str(exc),
            exc_info=True,
        )
    finally:
        logger.info("ws_user_connection_closed", user_id=user_id)


# ── Private helpers ──────────────────────────────────────────────────────────

async def _replay_event_buffer(
    websocket: WebSocket,
    search_id: str,
    redis_client: aioredis.Redis,
) -> None:
    """
    Read all events from ``evtbuf:{search_id}`` and send them to *websocket*
    in order, wrapped in a ``buffered_events`` envelope.

    If the buffer is empty or the Redis read fails the function returns
    silently — it is not critical for the connection to succeed.
    """
    buf_key = f"{_EVTBUF_PREFIX}{search_id}"

    try:
        raw_events: list[str] = await redis_client.lrange(buf_key, 0, -1)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "ws_buffer_read_failed",
            search_id=search_id,
            error=str(exc),
        )
        return

    if not raw_events:
        logger.debug("ws_no_buffered_events", search_id=search_id)
        return

    # Parse each stored JSON string back to a dict.
    parsed: list[dict] = []
    for raw in raw_events:
        try:
            parsed.append(json.loads(raw))
        except (json.JSONDecodeError, TypeError):
            logger.warning(
                "ws_buffer_bad_json",
                search_id=search_id,
                raw=raw[:200],
            )

    if not parsed:
        return

    logger.info(
        "ws_replaying_buffered_events",
        search_id=search_id,
        count=len(parsed),
    )

    try:
        # Send a single envelope containing all buffered events so the client
        # can distinguish replayed history from live events.
        await websocket.send_json(
            {
                "type": "buffered_events",
                "search_id": search_id,
                "events": parsed,
            }
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "ws_buffer_send_failed",
            search_id=search_id,
            error=str(exc),
        )


async def _ping_loop(websocket: WebSocket, label: str) -> None:
    """
    Send a WebSocket ping frame every *_PING_INTERVAL* seconds.

    Exits when the socket is no longer connected or when the send raises,
    which signals the caller that the connection has been lost.
    """
    while True:
        await asyncio.sleep(_PING_INTERVAL)

        if websocket.client_state != WebSocketState.CONNECTED:
            logger.debug("ws_ping_socket_not_connected", label=label)
            return

        try:
            await websocket.send_json({"type": "ping"})
            logger.debug("ws_ping_sent", label=label)
        except Exception as exc:  # noqa: BLE001
            logger.debug("ws_ping_failed", label=label, error=str(exc))
            return


async def _message_reader(websocket: WebSocket, label: str) -> None:
    """
    Receive and process messages from the client until it disconnects.

    Supported client messages
    -------------------------
    ``{"action": "cancel"}``
        Acknowledge the cancel intent. The actual cancellation is handled by
        the backend API (DELETE /api/v1/searches/{search_id}); this side
        just logs and can forward the signal in the future.

    ``{"action": "pong"}``
        Optional client-side response to server pings. Logged at debug level.

    Any other message is logged and ignored, making the protocol forward-
    compatible without crashing on unknown actions.
    """
    while True:
        try:
            raw = await websocket.receive_text()
        except WebSocketDisconnect:
            logger.info("ws_client_sent_disconnect", label=label)
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "ws_receive_error",
                label=label,
                error=str(exc),
            )
            return

        try:
            message: dict = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            logger.debug("ws_received_non_json", label=label, raw=raw[:200])
            continue

        action = message.get("action")

        if action == "cancel":
            logger.info("ws_client_requested_cancel", label=label)
            # Future: publish a cancel signal to Redis so the worker stops.
            # For now we acknowledge receipt and let the client call the REST
            # DELETE endpoint to actually cancel the Celery task.
            try:
                await websocket.send_json(
                    {"type": "cancel_acknowledged", "label": label}
                )
            except Exception:  # noqa: BLE001
                return

        elif action == "pong":
            logger.debug("ws_client_pong", label=label)

        else:
            logger.debug(
                "ws_unknown_client_message",
                label=label,
                action=action,
                message=message,
            )
