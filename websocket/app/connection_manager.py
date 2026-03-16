"""
WebSocket connection manager.

Maintains a registry of active WebSocket connections grouped by search_id.
All mutation of the internal registry is serialised through an asyncio Lock
so it is safe to call from concurrent coroutines running inside the single
uvicorn event loop.

Design notes
------------
- One uvicorn worker means one event loop and one in-process registry.
  If the service is ever scaled to multiple replicas, sticky-session routing
  (e.g. nginx ip_hash or consistent hashing on search_id) must be used so
  that all connections belonging to the same search land on the same instance.
- Dead connections are pruned lazily during broadcast rather than eagerly on
  every write, which avoids a second lock acquisition in the hot path.
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from app.core.config import get_settings

import structlog

logger = structlog.get_logger(__name__)
settings = get_settings()


class ConnectionManager:
    """
    Manages WebSocket connections grouped by search_id.

    Rooms are created implicitly on the first connect and destroyed
    automatically when the last connection leaves.
    """

    def __init__(self) -> None:
        # search_id -> list of accepted WebSocket connections
        self._connections: dict[str, list[WebSocket]] = {}
        self._lock = asyncio.Lock()

    # ── Public interface ─────────────────────────────────────────────────────

    async def connect(self, search_id: str, websocket: WebSocket) -> None:
        """
        Accept the WebSocket handshake and register the connection in the
        room identified by *search_id*.

        The caller must NOT call ``websocket.accept()`` beforehand; this
        method does it.
        """
        await websocket.accept()
        async with self._lock:
            if search_id not in self._connections:
                self._connections[search_id] = []
            self._connections[search_id].append(websocket)

        logger.info(
            "ws_connected",
            search_id=search_id,
            room_size=len(self._connections[search_id]),
            total_connections=self.get_connection_count(),
        )

    async def disconnect(self, search_id: str, websocket: WebSocket) -> None:
        """
        Remove *websocket* from the room identified by *search_id* and
        delete the room entry if it becomes empty.
        """
        async with self._lock:
            room = self._connections.get(search_id)
            if room is None:
                return
            try:
                room.remove(websocket)
            except ValueError:
                # Already removed (e.g. pruned during broadcast).
                pass
            if not room:
                del self._connections[search_id]

        logger.info(
            "ws_disconnected",
            search_id=search_id,
            total_connections=self.get_connection_count(),
        )

    async def broadcast_to_search(self, search_id: str, message: dict[str, Any]) -> None:
        """
        Send *message* as JSON to every connection in the *search_id* room.

        Connections that have gone away since the last send are silently
        removed from the registry so they do not block future broadcasts.
        """
        async with self._lock:
            # Take a snapshot so we can iterate outside the lock if needed,
            # but since we are already under the lock we iterate directly.
            room = list(self._connections.get(search_id, []))

        if not room:
            logger.debug("broadcast_no_receivers", search_id=search_id)
            return

        dead: list[WebSocket] = []

        for ws in room:
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.send_json(message)
                else:
                    dead.append(ws)
            except Exception as exc:  # noqa: BLE001
                # RuntimeError, WebSocketDisconnect, or transport errors.
                logger.warning(
                    "broadcast_send_failed",
                    search_id=search_id,
                    error=str(exc),
                )
                dead.append(ws)

        if dead:
            async with self._lock:
                room_ref = self._connections.get(search_id)
                if room_ref is not None:
                    for ws in dead:
                        try:
                            room_ref.remove(ws)
                        except ValueError:
                            pass
                    if not room_ref:
                        del self._connections[search_id]

            logger.info(
                "broadcast_pruned_dead_connections",
                search_id=search_id,
                pruned=len(dead),
            )

    def get_connection_count(self) -> int:
        """Return the total number of active connections across all rooms."""
        return sum(len(conns) for conns in self._connections.values())

    def get_room_count(self) -> int:
        """Return the number of active search rooms."""
        return len(self._connections)
