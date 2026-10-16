"""Mock pipeline adapter — clearly labelled SIMULATED.

This adapter produces deterministic observations from a scripted scenario. It
exists so the UI, rule engine, persistence, and transport can be developed and
tested without an NVIDIA GPU or PipeGen. Every observation it emits has
``is_simulated=True`` and entity provenance ``simulated``. Nothing here is a
PipeGen inference result and nothing here may be presented as real evidence.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncIterator, Optional

from ..schemas import (
    BoundingBox,
    NormalizedEntity,
    Observation,
    PipelineStatus,
    Provenance,
    RunMode,
    SourceStatus,
)
from ..demo.scenarios import Scenario, workshop_scenario
from .base import AdapterMetadata, AdapterStatus, PipelineAdapter

ENTITY_WIDTH = 0.06
ENTITY_HEIGHT = 0.14


class MockPipelineAdapter(PipelineAdapter):
    kind = "mock"

    def __init__(
        self,
        *,
        scenario: Optional[Scenario] = None,
        source_id: str = "sim_source",
        fps: int = 15,
        start_time: Optional[datetime] = None,
    ) -> None:
        self.scenario = scenario or workshop_scenario()
        self.source_id = source_id
        self.fps = max(1, fps)
        self._start_time = start_time or datetime.now(tz=timezone.utc)
        self._monotonic_start = time.monotonic()
        self._running = False
        self._frame = 0
        self._last_observation_at: Optional[datetime] = None

    # -- interface ------------------------------------------------------
    @property
    def metadata(self) -> AdapterMetadata:
        return AdapterMetadata(
            adapter="MockPipelineAdapter",
            kind="mock",
            is_simulated=True,
            pipeline_version="mock-0.0.0",
            model_id="simulated-scene-script",
            precision="n/a (simulated)",
            engine_path=None,
            report_path=None,
            extra={"scenario": self.scenario.name},
        )

    def status(self) -> AdapterStatus:
        return AdapterStatus(
            pipeline_status=PipelineStatus.simulated if self._running else PipelineStatus.stopped,
            source_status=SourceStatus.connected if self._running else SourceStatus.unavailable,
            mode=RunMode.simulated,
            message="Simulated scene source (no GPU / PipeGen involved).",
            last_observation_at=self._last_observation_at,
            last_frame_at=self._last_observation_at,
        )

    async def start(self) -> None:
        self._running = True
        self._monotonic_start = time.monotonic()
        self._start_time = datetime.now(tz=timezone.utc)

    async def stop(self) -> None:
        self._running = False

    async def observe(self) -> AsyncIterator[Observation]:
        interval = 1.0 / self.fps
        while self._running:
            loop_start = time.monotonic()
            elapsed = loop_start - self._monotonic_start
            observation = self.build_observation(elapsed)
            self._last_observation_at = observation.timestamp
            yield observation
            sleep_for = interval - (time.monotonic() - loop_start)
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)

    # -- pure construction (used by tests) -----------------------------
    def scenario_elapsed(self, elapsed: float) -> float:
        if self.scenario.loop and self.scenario.duration > 0:
            return elapsed % self.scenario.duration
        return elapsed

    def build_observation(self, elapsed: float) -> Observation:
        local = self.scenario_elapsed(elapsed)
        timestamp = self._start_time + timedelta(seconds=elapsed)
        entities: list[NormalizedEntity] = []
        for track in self.scenario.tracks:
            point = track.position_at(local)
            if point is None:
                continue
            bbox = BoundingBox(
                x_min=_clamp(point.x - ENTITY_WIDTH / 2),
                y_min=_clamp(point.y - ENTITY_HEIGHT / 2),
                x_max=_clamp(point.x + ENTITY_WIDTH / 2),
                y_max=_clamp(point.y + ENTITY_HEIGHT / 2),
            )
            entities.append(
                NormalizedEntity(
                    track_id=track.track_id,
                    class_label=track.class_label,
                    bbox=bbox,
                    confidence=track.confidence,
                    provenance=Provenance.simulated,
                )
            )
        obs = Observation(
            observation_id=f"simobs_{uuid.uuid4().hex[:12]}",
            run_id="pending",
            source_id=self.source_id,
            timestamp=timestamp,
            frame_index=int(elapsed * self.fps),
            entities=entities,
            is_simulated=True,
            correlation_id=uuid.uuid4().hex[:12],
        )
        self._frame += 1
        return obs


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
