"""Aggregate all v1 API routers."""

from __future__ import annotations

from fastapi import APIRouter

from . import (
    routes_analytics,
    routes_events,
    routes_evidence,
    routes_pipeline,
    routes_regions,
    routes_rules,
    routes_runs,
    routes_system,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(routes_system.router)
api_router.include_router(routes_runs.router)
api_router.include_router(routes_events.router)
api_router.include_router(routes_rules.router)
api_router.include_router(routes_regions.router)
api_router.include_router(routes_analytics.router)
api_router.include_router(routes_evidence.router)
api_router.include_router(routes_pipeline.router)

__all__ = ["api_router"]
