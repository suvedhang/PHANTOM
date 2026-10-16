"""Pipeline adapter boundary.

Everything the API knows about an inference pipeline goes through
:class:`PipelineAdapter`. A mock adapter and a (contract-gated) real PipeGen
adapter implement it. The UI/rule engine only ever see normalized
:class:`Observation` objects, so the real PipeGen integration can be added
without touching the frontend or the rule engine.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import AsyncIterator, Literal, Optional

from ..schemas import (
    Observation,
    PipelineStatus,
    RunMode,
    SourceStatus,
)


@dataclass
class AdapterMetadata:
    """Normalized run metadata at the adapter boundary."""

    adapter: str
    kind: Literal["mock", "pipegen"]
    is_simulated: bool
    pipeline_version: Optional[str] = None
    model_id: Optional[str] = None
    precision: Optional[str] = None
    engine_path: Optional[str] = None
    report_path: Optional[str] = None
    extra: dict[str, object] = field(default_factory=dict)


@dataclass
class AdapterStatus:
    pipeline_status: PipelineStatus
    source_status: SourceStatus
    mode: RunMode
    message: str = ""
    retry_count: int = 0
    recoverable: bool = True
    last_observation_at: Optional[datetime] = None
    last_frame_at: Optional[datetime] = None


class AdapterError(RuntimeError):
    """Base class for adapter failures with a safe, user-facing message."""


class NotConfiguredError(AdapterError):
    """Raised when an adapter cannot run because required config is missing."""


class PipelineAdapter(ABC):
    """Interface implemented by all pipeline adapters."""

    @property
    @abstractmethod
    def metadata(self) -> AdapterMetadata: ...

    @abstractmethod
    def status(self) -> AdapterStatus: ...

    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    def observe(self) -> AsyncIterator[Observation]:
        """Yield normalized observations until stopped."""
        ...
