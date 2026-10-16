"""Versioned external contracts for PHANTOM.

These Pydantic models are the single source of truth for the payloads that
cross the API boundary (observations, tracks, rule evaluations, incidents,
health). JSON Schema mirrors live in ``packages/contracts/schema`` and the
frontend TypeScript types in ``apps/web/src/api/types.ts`` mirror these models.

Coordinate convention for all geometry: normalized image coordinates in the
closed range [0, 1], origin at the top-left, +x to the right, +y downwards.
A bounding box is ``[x_min, y_min, x_max, y_max]``. Normalized units are NOT
metres; they are image-space fractions. See docs/EVENT_SCHEMA.md.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = "1.0"


def utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


# --------------------------------------------------------------------------
# Enumerations (stable external values)
# --------------------------------------------------------------------------
class Severity(str, Enum):
    info = "info"
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class EventStatus(str, Enum):
    active = "active"
    acknowledged = "acknowledged"
    resolved = "resolved"
    dismissed = "dismissed"


class Provenance(str, Enum):
    observed = "observed"
    derived = "derived"
    configured = "configured"
    simulated = "simulated"


class RunMode(str, Enum):
    live = "live"
    file = "file"
    disconnected = "disconnected"
    simulated = "simulated"


class PipelineStatus(str, Enum):
    not_configured = "not_configured"
    configured = "configured"
    starting = "starting"
    running = "running"
    stopping = "stopping"
    stopped = "stopped"
    failed = "failed"
    simulated = "simulated"


class SourceStatus(str, Enum):
    unavailable = "unavailable"
    connecting = "connecting"
    connected = "connected"
    stale = "stale"
    disconnected = "disconnected"
    invalid = "invalid"


class TransportStatus(str, Enum):
    disabled = "disabled"
    connected = "connected"
    reconnecting = "reconnecting"
    failed = "failed"


class EvidenceStatus(str, Enum):
    missing = "missing"
    pending = "pending"
    captured = "captured"
    verified = "verified"
    invalid = "invalid"


class RuleType(str, Enum):
    region_entry = "region_entry"
    region_exit = "region_exit"
    dwell_time = "dwell_time"
    wrong_way = "wrong_way"
    count_threshold = "count_threshold"
    sequence = "sequence"
    unexpected_presence = "unexpected_presence"
    motionless_track = "motionless_track"
    boundary_crossing = "boundary_crossing"
    baseline_deviation = "baseline_deviation"


class EventAction(str, Enum):
    created = "created"
    updated = "updated"
    acknowledged = "acknowledged"
    resolved = "resolved"
    dismissed = "dismissed"
    reopened = "reopened"
    annotated = "annotated"
    cleared = "cleared"


# --------------------------------------------------------------------------
# Geometry
# --------------------------------------------------------------------------
class Point(BaseModel):
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)


class Polygon(BaseModel):
    """A closed polygon of normalized points. At least 3 points required."""

    points: list[Point] = Field(min_length=3)

    @model_validator(mode="after")
    def _validate(self) -> "Polygon":
        unique = {(round(p.x, 6), round(p.y, 6)) for p in self.points}
        if len(unique) < 3:
            raise ValueError("polygon must contain at least 3 distinct points")
        return self


# --------------------------------------------------------------------------
# Region contract
# --------------------------------------------------------------------------
class RegionModel(BaseModel):
    region_id: str
    name: str = Field(min_length=1)
    polygon: Polygon
    enabled: bool = True
    version: int = 1


class RegionCreate(BaseModel):
    region_id: Optional[str] = None
    name: str = Field(min_length=1)
    polygon: Polygon
    enabled: bool = True


# --------------------------------------------------------------------------
# Observation / track contracts
# --------------------------------------------------------------------------
class BoundingBox(BaseModel):
    """Normalized bounding box [x_min, y_min, x_max, y_max]."""

    x_min: float = Field(ge=0.0, le=1.0)
    y_min: float = Field(ge=0.0, le=1.0)
    x_max: float = Field(ge=0.0, le=1.0)
    y_max: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _ordered(self) -> "BoundingBox":
        if self.x_max < self.x_min or self.y_max < self.y_min:
            raise ValueError("bounding box max must be >= min")
        return self

    @property
    def center(self) -> Point:
        return Point(x=(self.x_min + self.x_max) / 2, y=(self.y_min + self.y_max) / 2)

    @property
    def area(self) -> float:
        return max(0.0, self.x_max - self.x_min) * max(0.0, self.y_max - self.y_min)


class NormalizedEntity(BaseModel):
    """A single detected entity within a frame.

    ``confidence`` is the detector's raw score when the source pipeline
    provides one. It is NOT a calibrated event probability.
    """

    track_id: Optional[str] = None
    class_label: str = Field(min_length=1)
    bbox: Optional[BoundingBox] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    provenance: Provenance = Provenance.observed


class Observation(BaseModel):
    """A normalized, versioned frame observation."""

    schema_version: str = SCHEMA_VERSION
    observation_id: str
    run_id: str
    source_id: str
    timestamp: datetime
    frame_index: int = Field(ge=0)
    entities: list[NormalizedEntity] = Field(default_factory=list)
    is_simulated: bool = False
    raw_reference: Optional[str] = None
    correlation_id: Optional[str] = None

    @field_validator("timestamp")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware (UTC)")
        return value


class Track(BaseModel):
    """Run-scoped track state exposed through the API."""

    track_id: str
    run_id: str
    class_label: str
    first_seen: datetime
    last_seen: datetime
    lifecycle: Literal["active", "expired"] = "active"
    recent_positions: list[Point] = Field(default_factory=list)
    provenance: Provenance = Provenance.derived


# --------------------------------------------------------------------------
# Rule contract
# --------------------------------------------------------------------------
class RuleConfig(BaseModel):
    """Rule-type specific configuration.

    Only the fields relevant to the rule's ``type`` are populated. Validation
    of required fields lives in the rule engine to keep this contract stable
    across rule additions.
    """

    region_id: Optional[str] = None
    class_filter: list[str] = Field(default_factory=list)
    dwell_seconds: Optional[float] = Field(default=None, gt=0)
    count_threshold: Optional[int] = Field(default=None, gt=0)
    sustain_seconds: Optional[float] = Field(default=None, gt=0)
    allowed_direction_deg: Optional[float] = Field(default=None, ge=0, le=360)
    min_displacement: Optional[float] = Field(default=None, ge=0, le=1.0)
    # Newly-added optional knobs (defaults are safe / conservative).
    min_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    cooldown_seconds: float = Field(default=30.0, ge=0)
    dedup_seconds: float = Field(default=2.0, ge=0)


class RuleDefinition(BaseModel):
    rule_id: str
    name: str = Field(min_length=1)
    description: str = ""
    type: RuleType
    config: RuleConfig = Field(default_factory=RuleConfig)
    severity: Severity = Severity.medium
    enabled: bool = True
    version: int = 1
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class RuleCreate(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""
    type: RuleType
    config: RuleConfig = Field(default_factory=RuleConfig)
    severity: Severity = Severity.medium
    enabled: bool = True


class RuleUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1)
    description: Optional[str] = None
    config: Optional[RuleConfig] = None
    severity: Optional[Severity] = None
    enabled: Optional[bool] = None


# --------------------------------------------------------------------------
# Rule evaluation contract
# --------------------------------------------------------------------------
class EvaluationOutcome(str, Enum):
    triggered = "triggered"
    not_triggered = "not_triggered"
    error = "error"


class RuleEvaluation(BaseModel):
    schema_version: str = SCHEMA_VERSION
    evaluation_id: str
    rule_id: str
    rule_version: int
    run_id: str
    observation_id: Optional[str] = None
    timestamp: datetime
    outcome: EvaluationOutcome
    condition: str
    observed_values: dict[str, object] = Field(default_factory=dict)
    threshold: dict[str, object] = Field(default_factory=dict)
    evidence_track_ids: list[str] = Field(default_factory=list)
    message: str = ""
    is_simulated: bool = False


# --------------------------------------------------------------------------
# Incident event contract
# --------------------------------------------------------------------------
class EventExplanation(BaseModel):
    """Deterministic explanation for an event.

    ``human`` is generated from structured facts only. ``machine`` carries the
    condition, observed values, threshold, and outcome so a consumer can
    re-derive the decision without natural-language parsing.
    """

    human: str
    machine: dict[str, object]
    generated_by: Literal["deterministic"] = "deterministic"


class IncidentEvent(BaseModel):
    schema_version: str = SCHEMA_VERSION
    event_id: str
    run_id: str
    source_id: str
    rule_id: str
    rule_version: int
    created_at: datetime
    first_seen: datetime
    last_seen: datetime
    severity: Severity
    status: EventStatus = EventStatus.active
    title: str
    provenance: Provenance
    is_simulated: bool = False
    correlation_id: Optional[str] = None
    explanation: EventExplanation
    evidence: dict[str, object] = Field(default_factory=dict)
    track_ids: list[str] = Field(default_factory=list)
    observation_ids: list[str] = Field(default_factory=list)
    evidence_quality: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class EventAuditEntry(BaseModel):
    audit_id: str
    event_id: str
    action: EventAction
    actor: str = "system"
    timestamp: datetime
    note: str = ""


class EventStatusUpdate(BaseModel):
    action: Literal["acknowledge", "resolve", "dismiss", "reopen", "annotate"]
    actor: str = "operator"
    note: str = ""

    @model_validator(mode="after")
    def _note_required_for_some(self) -> "EventStatusUpdate":
        if self.action in ("dismiss", "annotate") and not self.note.strip():
            raise ValueError(f"a note is required when action is '{self.action}'")
        return self


# --------------------------------------------------------------------------
# System contracts
# --------------------------------------------------------------------------
class PipelineInfo(BaseModel):
    status: PipelineStatus
    mode: RunMode
    adapter: str
    adapter_kind: Literal["mock", "pipegen"]
    configured: bool
    is_simulated: bool
    last_observation_at: Optional[datetime] = None
    last_successful_frame_at: Optional[datetime] = None
    stale: bool = False
    message: str = ""
    retry_count: int = 0
    recoverable: bool = True
    model_id: Optional[str] = None
    precision: Optional[str] = None
    engine_path: Optional[str] = None
    report_path: Optional[str] = None
    pipeline_version: Optional[str] = None


class TransportInfo(BaseModel):
    status: TransportStatus
    connected_clients: int = 0
    published: int = 0
    failed: int = 0
    dropped: int = 0
    mqtt_enabled: bool = False
    mqtt_connected: bool = False
    mqtt_topic_prefix: str = "phantom"


class SystemStatus(BaseModel):
    schema_version: str = SCHEMA_VERSION
    timestamp: datetime = Field(default_factory=utcnow)
    api_status: Literal["ok", "degraded"] = "ok"
    demo_mode: bool
    pipeline: PipelineInfo
    transport: TransportInfo
    source_status: SourceStatus
    active_run_id: Optional[str] = None
    last_event_at: Optional[datetime] = None
    recent_errors: list[str] = Field(default_factory=list)
    config: dict[str, object] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"] = "ok"
    app: str
    version: str
    timestamp: datetime = Field(default_factory=utcnow)
    database: Literal["ok", "error"] = "ok"
    detail: str = ""


# --------------------------------------------------------------------------
# Analytics
# --------------------------------------------------------------------------
class AnalyticsSummary(BaseModel):
    window_start: datetime
    window_end: datetime
    total_events: int
    active_events: int
    events_by_severity: dict[str, int]
    events_by_rule: dict[str, int]
    events_by_status: dict[str, int]
    events_over_time: list[dict[str, object]]
    average_active_duration_seconds: Optional[float] = None
    is_simulated: bool
    sample_count: int
    notes: list[str] = Field(default_factory=list)


class Paginated(BaseModel):
    items: list[object]
    total: int
    limit: int
    offset: int


class ApiError(BaseModel):
    error: str
    code: str
    detail: str = ""
    correlation_id: Optional[str] = None
