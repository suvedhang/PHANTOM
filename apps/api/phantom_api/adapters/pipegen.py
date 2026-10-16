"""PipeGen adapter boundary (real Track A pipeline).

STATUS: CONTRACT UNVERIFIED. The exact PipeGen v0.5.1 command/output contract
has not been confirmed in this environment (no NVIDIA host, no installed
pipegen). This adapter therefore:

* detects whether PipeGen is *configured* (executable + export dir);
* performs a preflight of local, verifiable facts (path exists, version
  string) using safe (non-shell) subprocess calls;
* reads run metadata ONLY from files it can locate and parse;
* REFUSES to start a run and raises a transparent, actionable error until the
  real run contract is verified.

It never invents CLI flags, never fabricates a TensorRT engine, speed report,
FPS, latency, or a Pipeline IR graph. See docs/PIPEGEN_INTEGRATION.md and
docs/PIPEGEN_SETUP.md for exactly what must be verified before this adapter can
run.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator, Optional

from ..config import Settings
from ..schemas import (
    Observation,
    PipelineStatus,
    RunMode,
    SourceStatus,
)
from .base import (
    AdapterMetadata,
    AdapterStatus,
    NotConfiguredError,
    PipelineAdapter,
)

# Documented shape of an export metadata file. PipeGen's real output must be
# mapped onto this before the adapter can present values. Field names here are
# PHANTOM's, NOT asserted to match PipeGen's actual output.
EXPECTED_METADATA_FILENAME = "run_metadata.json"


@dataclass
class PreflightCheck:
    name: str
    passed: bool
    detail: str


class PipeGenAdapter(PipelineAdapter):
    kind = "pipegen"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._running = False
        self._source: Optional[str] = None
        self._metadata_file = self._locate_metadata_file()

    # -- interface ------------------------------------------------------
    @property
    def metadata(self) -> AdapterMetadata:
        meta = self._read_metadata_file()
        return AdapterMetadata(
            adapter="PipeGenAdapter",
            kind="pipegen",
            is_simulated=False,
            pipeline_version=meta.get("pipeline_version") or self._settings.pipegen_expected_version,
            model_id=meta.get("model_id"),
            precision=meta.get("precision"),
            engine_path=meta.get("engine_path"),
            report_path=meta.get("report_path"),
            extra={"export_dir": self._settings.pipegen_export_dir or None},
        )

    def status(self) -> AdapterStatus:
        configured = self._settings.pipegen_configured
        if not configured:
            return AdapterStatus(
                pipeline_status=PipelineStatus.not_configured,
                source_status=SourceStatus.unavailable,
                mode=RunMode.disconnected,
                message=(
                    "PipeGen is not configured. Set PHANTOM_PIPEGEN_EXECUTABLE and "
                    "PHANTOM_PIPEGEN_EXPORT_DIR. See docs/PIPEGEN_SETUP.md."
                ),
                recoverable=True,
            )
        if self._running:
            return AdapterStatus(
                pipeline_status=PipelineStatus.running,
                source_status=SourceStatus.connected,
                mode=RunMode.live,
                message="PipeGen run reported as running (unverified contract).",
            )
        return AdapterStatus(
            pipeline_status=PipelineStatus.configured,
            source_status=SourceStatus.unavailable,
            mode=RunMode.disconnected,
            message=(
                "PipeGen paths are configured but the run contract is unverified; "
                "a live run cannot be started by PHANTOM yet."
            ),
        )

    async def start(self) -> None:
        if not self._settings.pipegen_configured:
            raise NotConfiguredError(
                "PipeGen is not configured. Set PHANTOM_PIPEGEN_EXECUTABLE and "
                "PHANTOM_PIPEGEN_EXPORT_DIR, then re-run preflight. See "
                "docs/PIPEGEN_SETUP.md."
            )
        raise NotConfiguredError(
            "The PipeGen run contract has not been verified in this environment. "
            "PHANTOM will not fabricate a run. Verify the exact five-stage command "
            "and output format, record it in apps/api/phantom_api/adapters/pipegen.py, "
            "and remove this guard. See docs/PIPEGEN_INTEGRATION.md."
        )

    async def stop(self) -> None:
        self._running = False

    async def observe(self) -> AsyncIterator[Observation]:
        # No verified observation stream exists. Yield nothing; the run manager
        # will surface a clear disconnected state rather than fake data.
        if False:  # pragma: no cover - documents the intended generator type
            yield  # type: ignore[unreachable]
        return

    # -- preflight ------------------------------------------------------
    def preflight(self) -> list[PreflightCheck]:
        """Return verifiable local checks. Does not prove the pipeline works."""
        checks: list[PreflightCheck] = []
        exe = self._settings.pipegen_executable.strip()
        export = self._settings.pipegen_export_dir.strip()

        checks.append(
            PreflightCheck(
                "executable_configured",
                bool(exe),
                exe or "PHANTOM_PIPEGEN_EXECUTABLE is empty",
            )
        )
        if exe:
            resolved = shutil.which(exe) or (exe if Path(exe).exists() else "")
            checks.append(
                PreflightCheck(
                    "executable_found",
                    bool(resolved),
                    resolved or f"'{exe}' was not found on PATH or as a file",
                )
            )
            version = self._probe_version(exe)
            checks.append(
                PreflightCheck(
                    "version_probe",
                    version is not None,
                    version or "could not read `--version` (command/contract unverified)",
                )
            )

        export_path = Path(export) if export else None
        checks.append(
            PreflightCheck(
                "export_dir_configured",
                bool(export),
                export or "PHANTOM_PIPEGEN_EXPORT_DIR is empty",
            )
        )
        if export_path is not None:
            checks.append(
                PreflightCheck(
                    "export_dir_exists",
                    export_path.exists(),
                    str(export_path) if export_path.exists() else "directory not found",
                )
            )
        checks.append(
            PreflightCheck(
                "run_metadata_present",
                self._metadata_file is not None,
                str(self._metadata_file)
                if self._metadata_file
                else f"{EXPECTED_METADATA_FILENAME} not found in export dir",
            )
        )
        return checks

    def _probe_version(self, executable: str) -> Optional[str]:
        """Best-effort version probe.

        Uses ``--version`` which is the conventional flag. If PipeGen uses a
        different flag the probe simply reports failure; it does not guess.
        """
        try:
            result = subprocess.run(  # noqa: S603 - fixed args, no shell
                [executable, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        output = (result.stdout or result.stderr or "").strip().splitlines()
        return output[0] if output else None

    # -- metadata -------------------------------------------------------
    def _locate_metadata_file(self) -> Optional[Path]:
        export = self._settings.pipegen_export_dir.strip()
        if not export:
            return None
        candidate = Path(export) / EXPECTED_METADATA_FILENAME
        return candidate if candidate.exists() else None

    def _read_metadata_file(self) -> dict:
        if self._metadata_file is None:
            return {}
        try:
            data = json.loads(self._metadata_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}


__all__ = ["PipeGenAdapter", "PreflightCheck", "EXPECTED_METADATA_FILENAME"]
