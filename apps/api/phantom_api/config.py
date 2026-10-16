"""Application configuration.

All runtime configuration is loaded from environment variables (or a local
`.env` file) using pydantic-settings. Configuration is validated at startup so
that misconfiguration produces an actionable message instead of a crash deep
inside a request handler.
"""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repository root: apps/api/phantom_api/config.py -> up 4 levels.
REPO_ROOT = Path(__file__).resolve().parents[3]


def _resolve_path(value: str) -> Path:
    """Resolve a possibly-relative path against the repository root."""
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = (REPO_ROOT / path).resolve()
    return path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_prefix="PHANTOM_",
        extra="ignore",
    )

    host: str = "127.0.0.1"
    port: int = 8000
    db_path: str = "output/phantom.db"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    demo_mode: bool = True
    # Start the simulated scene source automatically in demo mode so the
    # dashboard is not empty on first load. Disable for a clean start in tests.
    autostart_mock: bool = True

    evidence_dir: str = "output/evidence"
    export_dir: str = "output/exports"
    log_dir: str = "output/logs"
    retention_days: int = 30

    ui_frame_rate: int = 8
    max_ingest_fps: int = 30
    ingest_queue_size: int = 256
    stale_after_seconds: float = 5.0

    mqtt_enabled: bool = False
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    mqtt_username: str = ""
    mqtt_password: str = ""
    mqtt_topic_prefix: str = "phantom"

    pipegen_executable: str = ""
    pipegen_export_dir: str = ""
    pipegen_expected_version: str = "0.5.1"

    app_name: str = "PHANTOM"
    app_version: str = "0.1.0-dev"

    @field_validator("ui_frame_rate", "max_ingest_fps")
    @classmethod
    def _positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("frame rates must be positive")
        return value

    @field_validator("stale_after_seconds")
    @classmethod
    def _positive_float(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("stale_after_seconds must be positive")
        return value

    # --- Derived paths -------------------------------------------------
    @property
    def db_file(self) -> Path:
        return _resolve_path(self.db_path)

    @property
    def evidence_path(self) -> Path:
        return _resolve_path(self.evidence_dir)

    @property
    def export_path(self) -> Path:
        return _resolve_path(self.export_dir)

    @property
    def log_path(self) -> Path:
        return _resolve_path(self.log_dir)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def pipegen_configured(self) -> bool:
        return bool(self.pipegen_executable.strip() and self.pipegen_export_dir.strip())

    def ensure_directories(self) -> None:
        for path in (self.db_file.parent, self.evidence_path, self.export_path, self.log_path):
            path.mkdir(parents=True, exist_ok=True)

    def redacted(self) -> dict[str, object]:
        """Configuration summary safe to return from a status endpoint."""
        return {
            "app_name": self.app_name,
            "app_version": self.app_version,
            "host": self.host,
            "port": self.port,
            "db_path": str(self.db_file),
            "demo_mode": self.demo_mode,
            "autostart_mock": self.autostart_mock,
            "retention_days": self.retention_days,
            "ui_frame_rate": self.ui_frame_rate,
            "max_ingest_fps": self.max_ingest_fps,
            "stale_after_seconds": self.stale_after_seconds,
            "cors_origins": self.cors_origin_list,
            "mqtt": {
                "enabled": self.mqtt_enabled,
                "host": self.mqtt_host,
                "port": self.mqtt_port,
                "topic_prefix": self.mqtt_topic_prefix,
                "username_set": bool(self.mqtt_username),
                "password_set": bool(self.mqtt_password),
            },
            "pipegen": {
                "configured": self.pipegen_configured,
                "executable_set": bool(self.pipegen_executable.strip()),
                "export_dir_set": bool(self.pipegen_export_dir.strip()),
                "export_dir": self.pipegen_export_dir.strip() or None,
                "expected_version": self.pipegen_expected_version,
            },
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()


def validate_startup_configuration(settings: Settings) -> list[str]:
    """Return a list of human-readable configuration problems.

    Empty list means the configuration is safe to start with.
    """
    problems: list[str] = []

    if not settings.demo_mode and not settings.pipegen_configured:
        problems.append(
            "DEMO_MODE is false but PipeGen is not configured. Set "
            "PHANTOM_PIPEGEN_EXECUTABLE and PHANTOM_PIPEGEN_EXPORT_DIR, or enable "
            "PHANTOM_DEMO_MODE=true for simulated development. See "
            "docs/TROUBLESHOOTING.md."
        )

    if settings.mqtt_enabled and not settings.mqtt_host.strip():
        problems.append("MQTT is enabled but PHANTOM_MQTT_HOST is empty.")

    return problems


def main() -> int:
    """Small CLI used by `python -m phantom_api.config` for config checks."""
    settings = get_settings()
    problems = validate_startup_configuration(settings)
    for problem in problems:
        print(f"CONFIG ERROR: {problem}", file=sys.stderr)
    if not problems:
        print("Configuration OK")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
