"""PipeGen adapter boundary tests (no NVIDIA host required)."""

from __future__ import annotations

import asyncio
import json

import pytest

from phantom_api.adapters.base import NotConfiguredError
from phantom_api.adapters.pipegen import EXPECTED_METADATA_FILENAME, PipeGenAdapter
from phantom_api.config import Settings
from phantom_api.schemas import PipelineStatus


def base_settings(**overrides) -> Settings:
    values = {
        "demo_mode": True,
        "pipegen_executable": "",
        "pipegen_export_dir": "",
    }
    values.update(overrides)
    return Settings(**values)


def test_status_not_configured_when_empty() -> None:
    adapter = PipeGenAdapter(base_settings())
    assert adapter.status().pipeline_status == PipelineStatus.not_configured


def test_start_raises_when_not_configured() -> None:
    adapter = PipeGenAdapter(base_settings())
    with pytest.raises(NotConfiguredError):
        asyncio.run(adapter.start())


def test_start_raises_when_configured_but_unverified() -> None:
    settings = base_settings(
        pipegen_executable="C:/fake/pipegen", pipegen_export_dir="C:/fake/export"
    )
    adapter = PipeGenAdapter(settings)
    with pytest.raises(NotConfiguredError):
        asyncio.run(adapter.start())


def test_status_configured_but_not_running() -> None:
    settings = base_settings(
        pipegen_executable="C:/fake/pipegen", pipegen_export_dir="C:/fake/export"
    )
    adapter = PipeGenAdapter(settings)
    assert adapter.status().pipeline_status == PipelineStatus.configured


def test_preflight_reports_missing_configuration() -> None:
    adapter = PipeGenAdapter(base_settings())
    checks = {c.name: c for c in adapter.preflight()}
    assert checks["executable_configured"].passed is False
    assert checks["executable_configured"].detail


def test_preflight_reads_metadata_file(tmp_path) -> None:
    export = tmp_path / "export"
    export.mkdir()
    meta = {
        "pipeline_version": "0.5.1",
        "model_id": "verified-model",
        "precision": "fp16",
        "engine_path": "model.engine",
        "report_path": "speed_report.json",
    }
    (export / EXPECTED_METADATA_FILENAME).write_text(json.dumps(meta), encoding="utf-8")
    adapter = PipeGenAdapter(base_settings(pipegen_export_dir=str(export)))
    info = adapter.metadata
    assert info.model_id == "verified-model"
    assert info.precision == "fp16"
    assert info.report_path == "speed_report.json"
    assert info.is_simulated is False


def test_preflight_does_not_claim_ready() -> None:
    export_dir = "C:/fake/export"
    adapter = PipeGenAdapter(base_settings(pipegen_export_dir=export_dir))
    checks = {c.name: c for c in adapter.preflight()}
    # Executable not provided -> not configured.
    assert checks["executable_configured"].passed is False
