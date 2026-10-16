"""WebSocket fan-out hub.

Design (backpressure policy, documented):
* Every connected client has its own bounded queue.
* ``observation`` messages are *droppable*: if a client's queue is full they are
  discarded and counted (they are high-frequency UI-only updates and the events
  derived from them are persisted independently).
* All other messages (events, status, health) are *non-droppable*. If a client
  cannot keep up, the hub closes its connection (counted as a drop) so the
  client reconnects and re-syncs history from the REST API. The vision pipeline
  is never blocked by a slow browser.
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import WebSocket

from ..logging_config import get_logger

logger = get_logger("phantom.transport.ws")

DEFAULT_QUEUE_SIZE = 128
DROPPABLE_TYPES = {"observation"}
HEARTBEAT_SECONDS = 15.0


@dataclass
class _Client:
    client_id: str
    websocket: WebSocket
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=DEFAULT_QUEUE_SIZE))
    sender: Optional[asyncio.Task] = None


class WebSocketHub:
    def __init__(self, queue_size: int = DEFAULT_QUEUE_SIZE) -> None:
        self._queue_size = queue_size
        self._clients: dict[str, _Client] = {}
        self._lock = asyncio.Lock()
        self._heartbeat_task: Optional[asyncio.Task] = None
        self.published = 0
        self.failed = 0
        self.dropped = 0

    async def start(self) -> None:
        if self._heartbeat_task is None:
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def stop(self) -> None:
        if self._heartbeat_task is not None:
            self._heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._heartbeat_task
            self._heartbeat_task = None
        async with self._lock:
            clients = list(self._clients.values())
        for client in clients:
            await self._teardown(client)

    @property
    def client_count(self) -> int:
        return len(self._clients)

    async def register(self, client_id: str, websocket: WebSocket) -> _Client:
        await websocket.accept()
        client = _Client(
            client_id=client_id,
            websocket=websocket,
            queue=asyncio.Queue(maxsize=self._queue_size),
        )
        client.sender = asyncio.create_task(self._send_loop(client))
        async with self._lock:
            self._clients[client_id] = client
        logger.info("ws client connected", extra={"component": "ws", "run_id": client_id})
        return client

    async def unregister(self, client_id: str) -> None:
        async with self._lock:
            client = self._clients.pop(client_id, None)
        if client is not None:
            await self._teardown(client)

    async def _teardown(self, client: _Client) -> None:
        if client.sender is not None and not client.sender.done():
            client.sender.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await client.sender
        with contextlib.suppress(Exception):
            await client.websocket.close()

    async def broadcast(self, message_type: str, payload: dict[str, Any]) -> None:
        message = {
            "type": message_type,
            "ts": datetime.now(tz=timezone.utc).isoformat(),
            "payload": payload,
        }
        async with self._lock:
            clients = list(self._clients.values())
        droppable = message_type in DROPPABLE_TYPES
        for client in clients:
            if client.queue.full():
                if droppable:
                    self.dropped += 1
                    continue
                # Non-droppable and client is too slow: close it.
                self.dropped += 1
                logger.warning(
                    "ws slow client closed (queue full)",
                    extra={"component": "ws", "run_id": client.client_id},
                )
                asyncio.create_task(self.unregister(client.client_id))
                continue
            with contextlib.suppress(asyncio.QueueFull):
                client.queue.put_nowait(message)

    async def _send_loop(self, client: _Client) -> None:
        while True:
            message = await client.queue.get()
            try:
                await client.websocket.send_json(message)
                self.published += 1
            except Exception:  # noqa: BLE001 - transport boundary
                self.failed += 1
                await self.unregister(client.client_id)
                return

    async def _heartbeat_loop(self) -> None:
        while True:
            await asyncio.sleep(HEARTBEAT_SECONDS)
            await self.broadcast("heartbeat", {"server_time": datetime.now(tz=timezone.utc).isoformat()})

    def stats(self) -> dict[str, int]:
        return {
            "clients": len(self._clients),
            "published": self.published,
            "failed": self.failed,
            "dropped": self.dropped,
        }
