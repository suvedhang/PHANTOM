"""SQLAlchemy ORM models.

These mirror the domain contracts in ``schemas.py`` but add persistence
concerns (primary keys, indexes, UTC timestamps). Business logic must not live
here; use the repository and services instead.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class RegionRow(Base):
    __tablename__ = "regions"

    region_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    polygon: Mapped[list] = mapped_column(JSON, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class RuleRow(Base):
    __tablename__ = "rules"

    rule_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="medium")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    versions: Mapped[list["RuleVersionRow"]] = relationship(
        back_populates="rule", cascade="all, delete-orphan"
    )


class RuleVersionRow(Base):
    """Immutable snapshot of a rule version, kept for historical event review."""

    __tablename__ = "rule_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_id: Mapped[str] = mapped_column(ForeignKey("rules.rule_id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    rule: Mapped[RuleRow] = relationship(back_populates="versions")

    __table_args__ = (Index("ix_rule_versions_rule", "rule_id", "version"),)


class RunRow(Base):
    __tablename__ = "runs"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_id: Mapped[str] = mapped_column(String(64), nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    adapter: Mapped[str] = mapped_column(String(40), default="")
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    pipeline_version: Mapped[str | None] = mapped_column(String(60), nullable=True)
    model_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    precision: Mapped[str | None] = mapped_column(String(30), nullable=True)
    engine_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    report_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_observation_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    message: Mapped[str] = mapped_column(Text, default="")


class EventRow(Base):
    __tablename__ = "events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_id: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active")
    title: Mapped[str] = mapped_column(String(300), default="")
    provenance: Mapped[str] = mapped_column(String(20), default="derived")
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dedup_key: Mapped[str] = mapped_column(String(200), nullable=False)
    explanation: Mapped[dict] = mapped_column(JSON, nullable=False)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    track_ids: Mapped[list] = mapped_column(JSON, default=list)
    observation_ids: Mapped[list] = mapped_column(JSON, default=list)
    evidence_quality: Mapped[float | None] = mapped_column(Float, nullable=True)
    closed_reason: Mapped[str] = mapped_column(Text, default="")

    audits: Mapped[list["EventAuditRow"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_events_timestamp", "created_at"),
        Index("ix_events_severity", "severity"),
        Index("ix_events_status", "status"),
        Index("ix_events_rule", "rule_id"),
        Index("ix_events_run", "run_id"),
        Index("ix_events_dedup", "dedup_key"),
    )


class EventAuditRow(Base):
    __tablename__ = "event_audit"

    audit_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.event_id"), nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    actor: Mapped[str] = mapped_column(String(120), default="system")
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    note: Mapped[str] = mapped_column(Text, default="")

    event: Mapped[EventRow] = relationship(back_populates="audits")

    __table_args__ = (Index("ix_event_audit_event", "event_id"),)


class EvaluationRow(Base):
    __tablename__ = "evaluations"

    evaluation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    rule_id: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_version: Mapped[int] = mapped_column(Integer, nullable=False)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False)
    observation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (Index("ix_evaluations_rule", "rule_id"),)


class EvidenceArtifactRow(Base):
    __tablename__ = "evidence_artifacts"

    artifact_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    type: Mapped[str] = mapped_column(String(60), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    path: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(20), default="missing")
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MetricRow(Base):
    __tablename__ = "system_metrics"

    metric_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(20), default="")
    source: Mapped[str] = mapped_column(String(40), default="measured")
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (Index("ix_metrics_name", "name"),)


class AppConfigRow(Base):
    """Simple key/value store for non-sensitive operator preferences."""

    __tablename__ = "app_config"

    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
