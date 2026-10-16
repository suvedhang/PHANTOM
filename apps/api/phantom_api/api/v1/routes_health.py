"""Health endpoint (API readiness)."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from ...config import get_settings
from ...database import session_scope
from ...logging_config import get_logger
from ...schemas import HealthResponse

router = APIRouter(tags=["health"])
logger = get_logger("phantom.api.health")


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    db_state = "ok"
    detail = ""
    try:
        with session_scope() as session:
            session.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        db_state = "error"
        detail = "Database not reachable."
        logger.error("health db check failed: %s", exc, extra={"component": "health"})
    return HealthResponse(
        status="ok" if db_state == "ok" else "degraded",
        app=settings.app_name,
        version=settings.app_version,
        database=db_state,
        detail=detail,
    )
