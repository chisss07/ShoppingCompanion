"""
Redis pub/sub listener for real-time search events.

The worker publishes search progress events to channels named:

    ws:search:{search_id}

This listener subscribes to the pattern ``ws:search:*`` using Redis
pattern-subscribe (PSUBSCRIBE) so a single subscription covers every active
search without needing to re-subscribe when new searches start.

For each received message the listener:
  1. Extracts the search_id from the channel name.
  2. Appends the raw message to a per-search event buffer stored in Redis
     (key: ``evtbuf:{search_id}``, TTL: 300 s) so late-joining clients can
     replay history.
  3. Forwards the parsed message to the ConnectionManager for fan-out to all
     connected browser WebSockets.

Reconnection
------------
Redis pub/sub connections are long-lived TCP streams. On transient failures
(Redis restart, network blip) the listener catches the exception, waits with
exponential back-off (1 s → 2 s → 4 s … capped at 60 s), then reconnects.
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

import redis.asyncio as aioredis

import structlog

if TYPE_CHECKING:
    from app.connection_manager import ConnectionManager

logger = structlog.get_logger(__name__)

# pub/sub pattern that matches every search channel
_CHANNEL_PATTERN = "ws:search:*"

# Key prefix for the per-search event buffer stored in Redis
_EVTBUF_PREFIX = "evtbuf:"

# How long (seconds) to keep the event buffer after the last write
_EVTBUF_TTL = 300

# Back-off parameters for reconnection attempts
_BACKOFF_BASE = 1.0   # seconds
_BACKOFF_MAX = 60.0   # seconds
_BACKOFF_FACTOR = 2.0


class RedisEventListener:
    """
    Subscribes to the Redis pub/sub pattern ``ws:search:*`` and forwards
    events to the ConnectionManager.

    Runs as a long-lived background asyncio Task; created and cancelled by
    the FastAPI lifespan context manager in ``app.main``.
    """

    def __init__(self, redis_url: str, manager: "ConnectionManager") -> None:
        self.redis_url = redis_url
        self.manager = manager
        self._running = False
        self._redis: aioredis.Redis | None = None

    # ── Lifecycle ────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """
        Connect to Redis and start consuming pub/sub messages.

        Reconnects automatically with exponential back-off on any connection
        error. The loop exits cleanly when ``stop()`` is called.
        """
        self._running = True
        backoff = _BACKOFF_BASE

        while self._running:
            try:
                await self._run_listener_loop()
                # _run_listener_loop returns only when self._running is False
                # or when the pubsub stream ends normally.
            except asyncio.CancelledError:
                logger.info("redis_listener_cancelled")
                break
            except Exception as exc:  # noqa: BLE001
                if not self._running:
                    break
                logger.warning(
                    "redis_listener_error_reconnecting",
                    error=str(exc),
                    backoff_seconds=backoff,
                )
                try:
                    await asyncio.sleep(backoff)
                except asyncio.CancelledError:
                    break
                backoff = min(backoff * _BACKOFF_FACTOR, _BACKOFF_MAX)
            else:
                # Successful completion without exception — reset back-off.
                backoff = _BACKOFF_BASE

        await self._cleanup()
        logger.info("redis_listener_stopped")

    async def stop(self) -> None:
        """Signal the listener loop to exit after the current iteration."""
        self._running = False
        await self._cleanup()

    # ── Internal helpers ─────────────────────────────────────────────────────

    async def _run_listener_loop(self) -> None:
        """
        Open a Redis connection, subscribe to the channel pattern, and
        dispatch messages until self._running becomes False or an exception
        is raised.
        """
        logger.info("redis_listener_connecting", redis_url=self.redis_url)

        # A dedicated connection is used for pub/sub because once a client
        # issues SUBSCRIBE/PSUBSCRIBE it can no longer send regular commands.
        self._redis = aioredis.from_url(
            self.redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_keepalive=True,
        )

        # A separate client for issuing RPUSH / EXPIRE (regular commands).
        cmd_client = aioredis.from_url(
            self.redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
        )

        try:
            pubsub = self._redis.pubsub()
            await pubsub.psubscribe(_CHANNEL_PATTERN)
            logger.info("redis_listener_subscribed", pattern=_CHANNEL_PATTERN)

            async for raw_message in pubsub.listen():
                if not self._running:
                    break

                # pubsub.listen() yields a dict for every frame including the
                # initial subscription confirmation.  We only care about actual
                # data messages published by workers.
                if raw_message.get("type") != "pmessage":
                    continue

                await self._handle_message(raw_message, cmd_client)

            await pubsub.punsubscribe(_CHANNEL_PATTERN)
            await pubsub.aclose()
        finally:
            await cmd_client.aclose()
            if self._redis is not None:
                await self._redis.aclose()
                self._redis = None

    async def _handle_message(
        self,
        raw_message: dict,
        cmd_client: aioredis.Redis,
    ) -> None:
        """
        Process one pub/sub message frame.

        Channel format : ``ws:search:{search_id}``
        Message data   : JSON-encoded event dict published by a worker.
        """
        channel: str = raw_message.get("channel", "")
        data: str = raw_message.get("data", "")

        # ── 1. Extract search_id from channel name ───────────────────────────
        # Channel format: "ws:search:{search_id}"
        # We split on ":" with a maximum of 2 splits so search IDs that
        # themselves contain colons (e.g. UUIDs with custom separators) are
        # preserved intact.
        parts = channel.split(":", 2)
        if len(parts) != 3 or parts[0] != "ws" or parts[1] != "search":
            logger.warning("redis_listener_unexpected_channel", channel=channel)
            return

        search_id = parts[2]
        if not search_id:
            logger.warning("redis_listener_empty_search_id", channel=channel)
            return

        # ── 2. Parse the message JSON ────────────────────────────────────────
        try:
            message: dict = json.loads(data)
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning(
                "redis_listener_bad_json",
                channel=channel,
                error=str(exc),
                raw_data=data[:200],  # truncate for log safety
            )
            return

        logger.debug(
            "redis_listener_received",
            search_id=search_id,
            event_type=message.get("type"),
        )

        # ── 3. Append to event buffer in Redis ───────────────────────────────
        # Key: evtbuf:{search_id}
        # We store the raw JSON string so clients replay byte-for-byte identical
        # events to what live subscribers receive.
        buf_key = f"{_EVTBUF_PREFIX}{search_id}"
        try:
            pipe = cmd_client.pipeline()
            pipe.rpush(buf_key, data)
            pipe.expire(buf_key, _EVTBUF_TTL)
            await pipe.execute()
        except Exception as exc:  # noqa: BLE001
            # Buffer write failure is non-fatal; live broadcast still proceeds.
            logger.warning(
                "redis_listener_buffer_write_failed",
                search_id=search_id,
                error=str(exc),
            )

        # ── 4. Fan-out to connected WebSocket clients ────────────────────────
        await self.manager.broadcast_to_search(search_id, message)

    async def _cleanup(self) -> None:
        """Close the pub/sub Redis connection if it is still open."""
        if self._redis is not None:
            try:
                await self._redis.aclose()
            except Exception:  # noqa: BLE001
                pass
            self._redis = None
