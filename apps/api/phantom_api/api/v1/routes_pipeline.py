"""Pipeline status and preflight (PipeGen integration boundary)."""

from __future__ import annotations

from fastapi import APIRouter, Request

from ...api.deps import context_from
from ...adapters.pipegen import PipeGenAdapter

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.get("/status")
def pipeline_status(request: Request) -> dict:
    ctx = context_from(request)
    info = ctx.run_manager.pipeline_info()
    return {
        "pipeline": info.model_dump(mode="json"),
        "measurement_note": (
            "Reported values (model, precision, engine, report) come from the pipeline "
            "adapter when available. PHANTOM never fabricates FPS, latency, or TensorRT "
            "metrics. Locally measured application throughput, if shown, is labelled "
            "separately."
        ),
    }


@router.get("/preflight")
def pipeline_preflight(request: Request) -> dict:
    """Check whether the real PipeGen pipeline can run here.

    This reports verifiable local facts only; it does not claim the pipeline
    works. The real adapter refuses to start until its contract is verified.
    """
    ctx = context_from(request)
    adapter = PipeGenAdapter(ctx.settings)
    checks = adapter.preflight()
    return {
        "configured": ctx.settings.pipegen_configured,
        "expected_version": ctx.settings.pipegen_expected_version,
        "checks": [
            {"name": c.name, "passed": c.passed, "detail": c.detail} for c in checks
        ],
        "ready_to_run": False,
        "blocker": (
            "The PipeGen run contract is not verified. PHANTOM will not fabricate a "
            "run. See docs/PIPEGEN_INTEGRATION.md."
        ),
    }


@router.get("/export")
def pipeline_export(request: Request) -> dict:
    """Describe the export/evidence directories so they are discoverable.

    Paths are exposed because they are operator configuration, not secrets.
    """
    ctx = context_from(request)
    return {
        "export_dir": str(ctx.settings.export_path),
        "evidence_dir": str(ctx.settings.evidence_path),
        "pipegen_export_dir": ctx.settings.pipegen_export_dir.strip() or None,
    }
