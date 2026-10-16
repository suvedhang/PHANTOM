"""Optional MQTT publisher for external actionable events.

MQTT is optional: the dashboard works fully without it. Configuration is read
from environment variables; credentials are never logged. Raw video frames are
never published — only structured JSON event/status payloads.

Topic structure (configurable prefix, default ``phantom``):
* ``phantom/events``  — incident event created/updated/cleared payloads
* ``phantom/status``  — run / pipeline status transitions
* ``phantom/health``  — periodic health snapshots
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from typing import Any, Optional

from ..config import Settings
from ..logging_config import get_logger

logger = get_logger("phantom.transport.mqtt")

try:  # paho is optional at import time so tests can run without it installed.
    import paho.mqtt.client as mqtt

    _PAHO_AVAILABLE = True
except Exception:  # noqa: BLE001
    mqtt = None  # type: ignore[assignment]
    _PAHO_AVAILABLE = False


class MqttPublisher:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: Optional["mqtt.Client"] = None
        self._connected = False
        self._lock = threading.Lock()
        self.published = 0
        self.failed = 0

    @property
    def enabled(self) -> bool:
        return self._settings.mqtt_enabled

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def topic_prefix(self) -> str:
        return self._settings.mqtt_topic_prefix

    def connect(self) -> None:
        if not self.enabled:
            logger.info("MQTT disabled; skipping connect", extra={"component": "mqtt"})
            return
        if not _PAHO_AVAILABLE:
            logger.warning(
                "PHANTOM_MQTT_ENABLED is true but paho-mqtt is not installed.",
                extra={"component": "mqtt"},
            )
            return
        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id="phantom-api",
        )
        if self._settings.mqtt_username:
            client.username_pw_set(
                self._settings.mqtt_username, self._settings.mqtt_password or None
            )
        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        try:
            client.connect_async(self._settings.mqtt_host, self._settings.mqtt_port, keepalive=30)
            client.loop_start()
            self._client = client
        except Exception as exc:  # noqa: BLE001 - transport boundary
            logger.warning("MQTT connect failed: %s", exc, extra={"component": "mqtt"})

    def disconnect(self) -> None:
        if self._client is not None:
            try:
                self._client.loop_stop()
                self._client.disconnect()
            except Exception:  # noqa: BLE001
                pass
            self._client = None
        self._connected = False

    def _on_connect(self, client, _userdata, _flags, reason_code, _properties=None) -> None:  # noqa: ANN001
        self._connected = True
        logger.info("MQTT connected", extra={"component": "mqtt"})

    def _on_disconnect(self, client, _userdata, _flags=None, reason_code=None, _properties=None) -> None:  # noqa: ANN001
        self._connected = False
        logger.info("MQTT disconnected", extra={"component": "mqtt"})

    def publish(self, channel: str, payload: dict[str, Any]) -> bool:
        """Publish a JSON payload to ``<prefix>/<channel>``.

        Returns True on success. Publishing is non-blocking; a broker outage
        increments the failure counter and never blocks the caller.
        """
        if not self.enabled or self._client is None:
            return False
        topic = f"{self._settings.mqtt_topic_prefix}/{channel}"
        body = json.dumps(
            {
                "published_at": datetime.now(tz=timezone.utc).isoformat(),
                **payload,
            },
            default=str,
        )
        try:
            with self._lock:
                info = self._client.publish(topic, body, qos=1)
            if info.rc == 0:
                self.published += 1
                return True
            self.failed += 1
            return False
        except Exception as exc:  # noqa: BLE001
            self.failed += 1
            logger.warning("MQTT publish failed: %s", exc, extra={"component": "mqtt"})
            return False

    def stats(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "connected": self._connected,
            "published": self.published,
            "failed": self.failed,
            "topic_prefix": self.topic_prefix,
        }
