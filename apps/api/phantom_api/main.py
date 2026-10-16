"""PHANTOM FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.v1 import api_router
from .api.v1 import routes_health, routes_ws
from .config import get_settings, validate_startup_configuration
from .context import AppContext, get_context, set_context
from .database import init_engine, init_schema, session_scope
from .demo import seed as demo_seed
from .logging_config import configure_logging, get_logger
from .services import evidence as evidence_service
from .services.event_service import EventService
from .services.run_manager import RunManager
from .transport.mqtt import MqttPublisher
from .transport.websocket import WebSocketHub

logger = get_logger("phantom.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_path)
    settings.ensure_directories()

    problems = validate_startup_configuration(settings)
    if problems:
        for problem in problems:
            logger.error("startup configuration error: %s", problem)
        raise RuntimeError(
            "PHANTOM cannot start with the current configuration:\n- "
            + "\n- ".join(problems)
            + "\nSee apps/api/.env.example and docs/TROUBLESHOOTING.md."
        )

    init_engine(settings)
    init_schema()

    hub = WebSocketHub()
    mqtt = MqttPublisher(settings)
    event_service = EventService(hub, mqtt)
    run_manager = RunManager(settings, hub, mqtt, event_service)

    ctx = AppContext(
        settings=settings,
        hub=hub,
        mqtt=mqtt,
        event_service=event_service,
        run_manager=run_manager,
    )
    set_context(ctx)
    app.state.ctx = ctx

    with session_scope() as session:
        evidence_service.seed_artifacts(session)
        if settings.demo_mode:
            demo_seed.seed_all(session)

    await hub.start()
    mqtt.connect()

    if settings.demo_mode and settings.autostart_mock:
        try:
            await run_manager.start_mock_run()
            logger.info("simulated run auto-started", extra={"component": "main"})
        except Exception as exc:  # noqa: BLE001
            logger.error("failed to auto-start simulated run: %s", exc)

    logger.info(
        "PHANTOM started (demo_mode=%s)", settings.demo_mode, extra={"component": "main"}
    )
    try:
        yield
    finally:
        await run_manager.stop_run()
        await hub.stop()
        mqtt.disconnect()
        logger.info("PHANTOM shutdown complete", extra={"component": "main"})


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="PHANTOM API",
        version=settings.app_version,
        description=(
            "Explainable visual rule monitoring. Converts normalized vision "
            "observations into deterministic, auditable rule-violation events."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(routes_health.router)
    app.include_router(api_router)
    app.include_router(routes_ws.router)

    @app.get("/", include_in_schema=False)
    def root() -> dict:
        return {
            "name": "PHANTOM API",
            "version": settings.app_version,
            "docs": "/docs",
            "health": "/health",
            "websocket": "/ws",
        }

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        correlation_id = None
        try:
            correlation_id = getattr(request.state, "correlation_id", None)
        except Exception:  # noqa: BLE001
            pass
        logger.exception(
            "unhandled error on %s %s", request.method, request.url.path,
            extra={"component": "api", "correlation_id": correlation_id},
        )
        # Never leak stack traces to clients.
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_error",
                "code": "internal_error",
                "detail": "An internal error occurred. Check server logs.",
                "correlation_id": correlation_id,
            },
        )

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    _settings = get_settings()
    uvicorn.run(
        "phantom_api.main:app",
        host=_settings.host,
        port=_settings.port,
        reload=False,
    )
