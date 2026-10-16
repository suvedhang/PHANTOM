"""Run manager: owns the active adapter, rule engine, and ingestion loop.

Only one run is active at a time (a deliberate simplification for the MVP).
The manager is transport-agnostic; it receives a WebSocket hub and MQTT
publisher by injection.
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Optional

from .. import repository as repo
from ..adapters.base import AdapterError, NotConfiguredError, PipelineAdapter
from ..adapters.mock import MockPipelineAdapter
from ..adapters.pipegen import PipeGenAdapter
from ..config import Settings
from ..database import session_scope
from ..logging_config import get_logger
from ..rule_engine.engine import RuleEngine
from ..schemas import (
    PipelineInfo,
    PipelineStatus,
    RunMode,
    SourceStatus,
)
from . import rules_service
from .event_service import EventService

logger = get_logger("phantom.run")

RULE_RELOAD_SECONDS = 1.0
UI_TRACK_TRAIL_POINTS = 20


class RunManager:
    def __init__(
        self,
        settings: Settings,
        hub,  # noqa: ANN001
        mqtt,  # noqa: ANN001
        event_service: EventService,
    ) -> None:
        self.settings = settings
        self._hub = hub
        self._mqtt = mqtt
        self._events = event_service
        self.engine = RuleEngine(stale_track_seconds=max(2.0, settings.stale_after_seconds))
        self._adapter: Optional[PipelineAdapter] = None
        self._task: Optional[asyncio.Task] = None
        self.run_id: Optional[str] = None
        self.source_id: Optional[str] = None
        self._pipeline_status = PipelineStatus.not_configured
        self._source_status = SourceStatus.unavailable
        self._mode = RunMode.disconnected
        self._message = "No active run."
        self._is_simulated = False
        self._last_observation_at: Optional[datetime] = None
        self._last_frame_at: Optional[datetime] = None
        self._last_ui_broadcast = 0.0
        self._retry_count = 0
        self._recoverable = True
        self._recent_errors: deque[str] = deque(maxlen=20)
        self._reload_counter = 0
        self._lock = asyncio.Lock()

    # -- public status --------------------------------------------------
    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    def is_stale(self) -> bool:
        if self._last_observation_at is None or not self.is_running:
            return False
        age = (datetime.now(tz=timezone.utc) - self._last_observation_at).total_seconds()
        return age > self.settings.stale_after_seconds

    def pipeline_info(self) -> PipelineInfo:
        meta = self._adapter.metadata if self._adapter else None
        from ..adapters.base import AdapterMetadata

        meta = meta or AdapterMetadata(
            adapter="none", kind="mock", is_simulated=False
        )
        return PipelineInfo(
            status=self._pipeline_status,
            mode=self._mode,
            adapter=meta.adapter,
            adapter_kind=meta.kind,
            configured=self.settings.pipegen_configured,
            is_simulated=self._is_simulated,
            last_observation_at=self._last_observation_at,
            last_successful_frame_at=self._last_frame_at,
            stale=self.is_stale(),
            message=self._message,
            retry_count=self._retry_count,
            recoverable=self._recoverable,
            model_id=meta.model_id,
            precision=meta.precision,
            engine_path=meta.engine_path,
            report_path=meta.report_path,
            pipeline_version=meta.pipeline_version,
        )

    def source_status(self) -> SourceStatus:
        if self.is_stale():
            return SourceStatus.stale
        return self._source_status

    def recent_errors(self) -> list[str]:
        return list(self._recent_errors)

    def _record_error(self, message: str) -> None:
        self._recent_errors.appendleft(message)
        logger.error(message, extra={"component": "run", "run_id": self.run_id})

    # -- lifecycle ------------------------------------------------------
    async def start_mock_run(self, *, fps: int = 15, source_id: str = "sim_source") -> str:
        async with self._lock:
            await self._stop_locked()
            adapter = MockPipelineAdapter(fps=fps, source_id=source_id)
            await adapter.start()
            self._begin_run(adapter, mode=RunMode.simulated, is_simulated=True)
            self._pipeline_status = PipelineStatus.simulated
            self._source_status = SourceStatus.connected
            self._message = "Simulated scene source running (no GPU / PipeGen involved)."
            self._spawn_loop()
            await self._broadcast_status()
            return self.run_id or ""

    async def start_real_run(self) -> None:
        """Attempt to start the real PipeGen pipeline.

        Raises :class:`NotConfiguredError` with an actionable message when the
        contract/config is unavailable. Never fabricates a run.
        """
        async with self._lock:
            await self._stop_locked()
            adapter = PipeGenAdapter(self.settings)
            self._adapter = adapter
            self._mode = RunMode.live
            self._is_simulated = False
            self._pipeline_status = PipelineStatus.starting
            self._source_status = SourceStatus.connecting
            self._message = "Starting PipeGen pipeline..."
            try:
                await adapter.start()
            except NotConfiguredError as exc:
                self._pipeline_status = (
                    PipelineStatus.not_configured
                    if not self.settings.pipegen_configured
                    else PipelineStatus.failed
                )
                self._source_status = SourceStatus.unavailable
                self._message = str(exc)
                self._recoverable = True
                self._record_error(str(exc))
                await self._broadcast_status()
                raise
            except AdapterError as exc:
                self._pipeline_status = PipelineStatus.failed
                self._source_status = SourceStatus.invalid
                self._message = str(exc)
                self._recoverable = False
                self._record_error(str(exc))
                await self._broadcast_status()
                raise

    async def stop_run(self) -> None:
        async with self._lock:
            await self._stop_locked()
        await self._broadcast_status()

    async def _stop_locked(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        if self._adapter is not None:
            with contextlib.suppress(Exception):
                await self._adapter.stop()
        if self.run_id is not None:
            with session_scope() as session:
                repo.end_run(session, self.run_id, "stopped", "Run stopped by operator.")
        self._pipeline_status = PipelineStatus.stopped if self.run_id else self._pipeline_status
        self._source_status = SourceStatus.disconnected
        self._mode = RunMode.disconnected
        self._message = "Run stopped."
        self._adapter = None
        self._last_observation_at = None

    def _begin_run(self, adapter: PipelineAdapter, *, mode: RunMode, is_simulated: bool) -> None:
        self._adapter = adapter
        self.engine = RuleEngine(stale_track_seconds=max(2.0, self.settings.stale_after_seconds))
        self.run_id = f"run_{uuid.uuid4().hex[:14]}"
        self.source_id = getattr(adapter, "source_id", "unknown_source")
        self._mode = mode
        self._is_simulated = is_simulated
        self._last_observation_at = None
        self._last_frame_at = None
        self._reload_counter = 0
        meta = adapter.metadata
        with session_scope() as session:
            repo.create_run(
                session,
                run_id=self.run_id,
                source_id=self.source_id or "unknown_source",
                mode=mode.value,
                status="running",
                adapter=meta.adapter,
                is_simulated=is_simulated,
                pipeline_version=meta.pipeline_version,
                model_id=meta.model_id,
                precision=meta.precision,
                engine_path=meta.engine_path,
                report_path=meta.report_path,
                message=self._message,
            )

    def _spawn_loop(self) -> None:
        self._task = asyncio.create_task(self._ingest_loop())

    # -- ingestion ------------------------------------------------------
    async def _ingest_loop(self) -> None:
        assert self._adapter is not None
        rules, regions = self._load_rules_and_regions()
        try:
            async for observation in self._adapter.observe():
                if self.run_id is None:
                    break
                observation = observation.model_copy(update={"run_id": self.run_id})
                self._last_observation_at = observation.timestamp
                self._last_frame_at = observation.timestamp

                self._reload_counter += 1
                if self._reload_counter % max(1, int(self.settings.max_ingest_fps * RULE_RELOAD_SECONDS)) == 0:
                    rules, regions = self._load_rules_and_regions()

                result = self.engine.process(observation, rules, regions)
                if result.treatments or result.evaluations:
                    with session_scope() as session:
                        repo.touch_run_observation(session, self.run_id, observation.timestamp)
                        for evaluation in result.evaluations:
                            repo.add_evaluation(
                                session,
                                evaluation_id=evaluation.evaluation_id,
                                rule_id=evaluation.rule_id,
                                rule_version=evaluation.rule_version,
                                run_id=evaluation.run_id,
                                observation_id=evaluation.observation_id,
                                timestamp=evaluation.timestamp,
                                outcome=evaluation.outcome.value,
                                payload=evaluation.model_dump(mode="json"),
                                is_simulated=evaluation.is_simulated,
                            )
                    for treatment in result.treatments:
                        with session_scope() as session:
                            with contextlib.suppress(Exception):
                                await self._events.handle_treatment(
                                    session,
                                    treatment,
                                    self.engine,
                                    run_id=self.run_id,
                                    source_id=self.source_id or "unknown_source",
                                    correlation_id=observation.correlation_id,
                                )

                await self._maybe_broadcast_observation(observation)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - ingestion boundary
            self._pipeline_status = PipelineStatus.failed
            self._recoverable = False
            self._message = f"Pipeline failed: {exc}"
            self._record_error(str(exc))
            if self.run_id is not None:
                with session_scope() as session:
                    repo.end_run(session, self.run_id, "failed", str(exc))
            await self._broadcast_status()

    def _load_rules_and_regions(self):  # noqa: ANN202
        with session_scope() as session:
            rule_rows = repo.list_rules(session)
            region_rows = repo.list_regions(session)
            rules = [rules_service.rule_row_to_definition(r) for r in rule_rows if r.enabled]
            regions = rules_service.regions_by_id(region_rows)
        return rules, regions

    async def _maybe_broadcast_observation(self, observation) -> None:  # noqa: ANN001
        now = asyncio.get_event_loop().time()
        if now - self._last_ui_broadcast < 1.0 / max(1, self.settings.ui_frame_rate):
            return
        self._last_ui_broadcast = now
        if self._hub is None:
            return
        tracks = [
            {
                "track_id": state.track_id,
                "class_label": state.class_label,
                "provenance": "derived",
                "recent_positions": [
                    {"x": p.x, "y": p.y} for (_, p) in list(state.positions)[-UI_TRACK_TRAIL_POINTS:]
                ],
            }
            for state in self.engine.track_snapshot()
        ]
        await self._hub.broadcast(
            "observation",
            {
                "observation_id": observation.observation_id,
                "run_id": observation.run_id,
                "source_id": observation.source_id,
                "frame_index": observation.frame_index,
                "timestamp": observation.timestamp.isoformat(),
                "is_simulated": observation.is_simulated,
                "entities": [e.model_dump(mode="json") for e in observation.entities],
                "tracks": tracks,
            },
        )

    async def _broadcast_status(self) -> None:
        if self._hub is None:
            return
        await self._hub.broadcast("run_status", self.pipeline_info().model_dump(mode="json"))


__all__ = ["RunManager"]
