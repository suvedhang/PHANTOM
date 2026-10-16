"""Application context: shared singletons wired once at startup.

Held on ``app.state.ctx`` so route handlers can access services without global
mutable state scattered through modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from .config import Settings
from .services.event_service import EventService
from .services.run_manager import RunManager
from .transport.mqtt import MqttPublisher
from .transport.websocket import WebSocketHub


@dataclass
class AppContext:
    settings: Settings
    hub: WebSocketHub
    mqtt: MqttPublisher
    event_service: EventService
    run_manager: RunManager
    started_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    schema_ready: bool = True


_context: Optional[AppContext] = None


def set_context(context: AppContext) -> None:
    global _context
    _context = context


def get_context() -> AppContext:
    if _context is None:
        raise RuntimeError("Application context not initialized.")
    return _context
