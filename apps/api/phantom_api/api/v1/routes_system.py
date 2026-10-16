"""System status, config, and recent errors."""

from __future__ import annotations

from fastapi import APIRouter, Request

from ...api.deps import context_from
from ...logging_config import get_logger
from ...repository import latest_event
from ...database import session_scope
from ...schemas import RunMode, SystemStatus, TransportStatus

router = APIRouter(prefix="/system", tags=["system"])
logger = get_logger("phantom.api.system")


def _build_status(ctx) -> SystemStatus:  # noqa: ANN001
    pipeline = ctx.run_manager.pipeline_info()
    hub_stats = ctx.hub.stats()
    mqtt_stats = ctx.mqtt.stats()

    if mqtt_stats["enabled"]:
        transport_status = (
            TransportStatus.connected if mqtt_stats["connected"] else TransportStatus.reconnecting
        )
    else:
        transport_status = (
            TransportStatus.connected if hub_stats["clients"] > 0 else TransportStatus.disabled
        )

    last_event_at = None
    with session_scope() as session:
        row = latest_event(session)
        if row is not None:
            last_event_at = row.created_at

    api_status = "ok" if pipeline.status.value not in ("failed",) else "degraded"

    return SystemStatus(
        api_status=api_status,
        demo_mode=ctx.settings.demo_mode,
        pipeline=pipeline,
        transport={
            "status": transport_status,
            "connected_clients": hub_stats["clients"],
            "published": hub_stats["published"],
            "failed": hub_stats["failed"] + mqtt_stats["failed"],
            "dropped": hub_stats["dropped"],
            "mqtt_enabled": mqtt_stats["enabled"],
            "mqtt_connected": mqtt_stats["connected"],
            "mqtt_topic_prefix": mqtt_stats["topic_prefix"],
        },
        source_status=ctx.run_manager.source_status(),
        active_run_id=ctx.run_manager.run_id,
        last_event_at=last_event_at,
        recent_errors=ctx.run_manager.recent_errors(),
        config=ctx.settings.redacted(),
    )


@router.get("/status", response_model=SystemStatus)
def system_status(request: Request) -> SystemStatus:
    return _build_status(context_from(request))


@router.get("/config")
def system_config(request: Request) -> dict:
    """Redacted configuration. Never returns secrets."""
    ctx = context_from(request)
    return {"config": ctx.settings.redacted()}


@router.get("/errors")
def system_errors(request: Request) -> dict:
    ctx = context_from(request)
    return {"errors": ctx.run_manager.recent_errors()}
