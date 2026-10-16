"""Shared test configuration.

Environment variables are set before the application is imported so that the
cached settings and database paths point at a temporary directory. The
simulated source is not auto-started; tests control run lifecycle explicitly.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

_TMP = Path(tempfile.mkdtemp(prefix="phantom_test_"))

os.environ.setdefault("PHANTOM_HOST", "127.0.0.1")
os.environ["PHANTOM_DB_PATH"] = str(_TMP / "phantom.db")
os.environ["PHANTOM_AUTOSTART_MOCK"] = "false"
os.environ["PHANTOM_DEMO_MODE"] = "true"
os.environ["PHANTOM_MQTT_ENABLED"] = "false"
os.environ["PHANTOM_EVIDENCE_DIR"] = str(_TMP / "evidence")
os.environ["PHANTOM_EXPORT_DIR"] = str(_TMP / "exports")
os.environ["PHANTOM_LOG_DIR"] = str(_TMP / "logs")


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient

    from phantom_api.config import get_settings
    from phantom_api.database import reset_runtime_state
    from phantom_api.main import create_app

    db_file = get_settings().db_file
    for suffix in ("", "-wal", "-shm"):
        path = db_file.parent / (db_file.name + suffix)
        if path.exists():
            path.unlink()
    reset_runtime_state()
    get_settings.cache_clear()

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client
    reset_runtime_state()
