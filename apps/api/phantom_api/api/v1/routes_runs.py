"""Run listing and control."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ...adapters.base import NotConfiguredError
from ...api.deps import context_from
from ...database import session_scope
from ...logging_config import get_logger
from ...repository import list_runs
from ...schemas import RunMode

router = APIRouter(prefix="/runs", tags=["runs"])
logger = get_logger("phantom.api.runs")

MAX_RUNS = 100


class StartRunRequest(BaseModel):
    mode: str = "mock"  # "mock" | "real"
    fps: int = 15


class StopRunResponse(BaseModel):
    ok: bool
    message: str


def _serialize_run(row) -> dict:  # noqa: ANN001
    return {
        "run_id": row.run_id,
        "source_id": row.source_id,
        "mode": row.mode,
        "status": row.status,
        "adapter": row.adapter,
        "is_simulated": row.is_simulated,
        "pipeline_version": row.pipeline_version,
        "model_id": row.model_id,
        "precision": row.precision,
        "engine_path": row.engine_path,
        "report_path": row.report_path,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "ended_at": row.ended_at.isoformat() if row.ended_at else None,
        "last_observation_at": row.last_observation_at.isoformat() if row.last_observation_at else None,
        "message": row.message,
    }


@router.get("")
def get_runs(request: Request, limit: int = 50) -> dict:
    limit = max(1, min(limit, MAX_RUNS))
    with session_scope() as session:
        rows = list_runs(session, limit=limit)
    return {"items": [_serialize_run(r) for r in rows]}


@router.get("/active")
def get_active_run(request: Request) -> dict:
    ctx = context_from(request)
    return {
        "active_run_id": ctx.run_manager.run_id,
        "pipeline": ctx.run_manager.pipeline_info().model_dump(mode="json"),
    }


@router.get("/{run_id}")
def get_run(request: Request, run_id: str) -> dict:
    from ...repository import get_run as repo_get_run

    with session_scope() as session:
        row = repo_get_run(session, run_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found.")
    return _serialize_run(row)


@router.post("")
async def start_run(request: Request, body: StartRunRequest) -> dict:
    ctx = context_from(request)
    mode = body.mode.lower()
    if mode == "mock":
        run_id = await ctx.run_manager.start_mock_run(fps=body.fps)
        return {
            "ok": True,
            "run_id": run_id,
            "is_simulated": True,
            "message": "Simulated run started. Data is clearly labelled SIMULATED.",
        }
    if mode == "real":
        if ctx.settings.demo_mode:
            raise HTTPException(
                status_code=409,
                detail=(
                    "DEMO_MODE is enabled. Set PHANTOM_DEMO_MODE=false on the NVIDIA host "
                    "and configure PipeGen before starting a real run."
                ),
            )
        try:
            await ctx.run_manager.start_real_run()
        except NotConfiguredError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {
            "ok": True,
            "run_id": ctx.run_manager.run_id,
            "is_simulated": False,
            "message": "Real PipeGen run started.",
        }
    raise HTTPException(status_code=422, detail="mode must be 'mock' or 'real'.")


@router.post("/stop", response_model=StopRunResponse)
async def stop_run(request: Request) -> StopRunResponse:
    ctx = context_from(request)
    await ctx.run_manager.stop_run()
    return StopRunResponse(ok=True, message="Run stopped.")
