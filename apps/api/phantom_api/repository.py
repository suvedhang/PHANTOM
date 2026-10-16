"""Persistence layer.

All database access goes through this module. Route handlers and services must
not build SQL directly. Functions take an explicit :class:`Session` so callers
control transaction boundaries (``session_scope``).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import db_models as m
from .schemas import IncidentEvent


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:20]}"


# --------------------------------------------------------------------------
# Regions
# --------------------------------------------------------------------------
def list_regions(session: Session) -> list[m.RegionRow]:
    return list(session.scalars(select(m.RegionRow).order_by(m.RegionRow.name)))


def get_region(session: Session, region_id: str) -> Optional[m.RegionRow]:
    return session.get(m.RegionRow, region_id)


def upsert_region(
    session: Session,
    *,
    region_id: Optional[str],
    name: str,
    polygon: list[dict[str, float]],
    enabled: bool = True,
) -> m.RegionRow:
    if region_id and (row := session.get(m.RegionRow, region_id)):
        row.name = name
        row.polygon = polygon
        row.enabled = enabled
        row.version += 1
        row.updated_at = _now()
        return row
    row = m.RegionRow(
        region_id=region_id or new_id("region"),
        name=name,
        polygon=polygon,
        enabled=enabled,
    )
    session.add(row)
    session.flush()
    return row


def delete_region(session: Session, region_id: str) -> bool:
    row = session.get(m.RegionRow, region_id)
    if row is None:
        return False
    session.delete(row)
    return True


# --------------------------------------------------------------------------
# Rules
# --------------------------------------------------------------------------
def list_rules(session: Session) -> list[m.RuleRow]:
    return list(session.scalars(select(m.RuleRow).order_by(m.RuleRow.name)))


def get_rule(session: Session, rule_id: str) -> Optional[m.RuleRow]:
    return session.get(m.RuleRow, rule_id)


def _snapshot(row: m.RuleRow) -> dict[str, Any]:
    return {
        "rule_id": row.rule_id,
        "name": row.name,
        "description": row.description,
        "type": row.type,
        "config": row.config,
        "severity": row.severity,
        "enabled": row.enabled,
        "version": row.version,
    }


def create_rule(
    session: Session,
    *,
    name: str,
    description: str,
    type_: str,
    config: dict[str, Any],
    severity: str,
    enabled: bool,
) -> m.RuleRow:
    row = m.RuleRow(
        rule_id=new_id("rule"),
        name=name,
        description=description,
        type=type_,
        config=config,
        severity=severity,
        enabled=enabled,
        version=1,
    )
    session.add(row)
    session.flush()
    session.add(
        m.RuleVersionRow(rule_id=row.rule_id, version=1, snapshot=_snapshot(row))
    )
    session.flush()
    return row


def update_rule(
    session: Session,
    row: m.RuleRow,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    config: Optional[dict[str, Any]] = None,
    severity: Optional[str] = None,
    enabled: Optional[bool] = None,
) -> m.RuleRow:
    changed = False
    for attr, value in (
        ("name", name),
        ("description", description),
        ("config", config),
        ("severity", severity),
        ("enabled", enabled),
    ):
        if value is not None:
            if getattr(row, attr) != value:
                setattr(row, attr, value)
                changed = True
    if changed:
        row.version += 1
        row.updated_at = _now()
        session.flush()
        session.add(
            m.RuleVersionRow(
                rule_id=row.rule_id, version=row.version, snapshot=_snapshot(row)
            )
        )
    session.flush()
    return row


def get_rule_version(session: Session, rule_id: str, version: int) -> Optional[m.RuleVersionRow]:
    return session.scalar(
        select(m.RuleVersionRow).where(
            m.RuleVersionRow.rule_id == rule_id, m.RuleVersionRow.version == version
        )
    )


# --------------------------------------------------------------------------
# Runs
# --------------------------------------------------------------------------
def create_run(
    session: Session,
    *,
    run_id: str,
    source_id: str,
    mode: str,
    status: str,
    adapter: str,
    is_simulated: bool,
    pipeline_version: Optional[str] = None,
    model_id: Optional[str] = None,
    precision: Optional[str] = None,
    engine_path: Optional[str] = None,
    report_path: Optional[str] = None,
    message: str = "",
) -> m.RunRow:
    row = m.RunRow(
        run_id=run_id,
        source_id=source_id,
        mode=mode,
        status=status,
        adapter=adapter,
        is_simulated=is_simulated,
        pipeline_version=pipeline_version,
        model_id=model_id,
        precision=precision,
        engine_path=engine_path,
        report_path=report_path,
        started_at=_now(),
        message=message,
    )
    session.add(row)
    session.flush()
    return row


def get_run(session: Session, run_id: str) -> Optional[m.RunRow]:
    return session.get(m.RunRow, run_id)


def list_runs(session: Session, limit: int = 50) -> list[m.RunRow]:
    return list(
        session.scalars(select(m.RunRow).order_by(m.RunRow.started_at.desc()).limit(limit))
    )


def latest_run(session: Session) -> Optional[m.RunRow]:
    return session.scalar(select(m.RunRow).order_by(m.RunRow.started_at.desc()).limit(1))


def touch_run_observation(session: Session, run_id: str, at: datetime) -> None:
    row = session.get(m.RunRow, run_id)
    if row is not None:
        row.last_observation_at = at


def end_run(session: Session, run_id: str, status: str, message: str = "") -> None:
    row = session.get(m.RunRow, run_id)
    if row is not None:
        row.status = status
        row.ended_at = _now()
        row.message = message
        session.flush()


# --------------------------------------------------------------------------
# Events
# --------------------------------------------------------------------------
def create_event(
    session: Session,
    event: IncidentEvent,
    *,
    dedup_key: str,
) -> m.EventRow:
    row = m.EventRow(
        event_id=event.event_id,
        run_id=event.run_id,
        source_id=event.source_id,
        rule_id=event.rule_id,
        rule_version=event.rule_version,
        created_at=event.created_at,
        first_seen=event.first_seen,
        last_seen=event.last_seen,
        severity=event.severity.value,
        status=event.status.value,
        title=event.title,
        provenance=event.provenance.value,
        is_simulated=event.is_simulated,
        correlation_id=event.correlation_id,
        dedup_key=dedup_key,
        explanation=event.explanation.model_dump(mode="json"),
        evidence=event.evidence,
        track_ids=event.track_ids,
        observation_ids=event.observation_ids,
        evidence_quality=event.evidence_quality,
    )
    session.add(row)
    session.flush()
    return row


def get_event(session: Session, event_id: str) -> Optional[m.EventRow]:
    return session.get(m.EventRow, event_id)


def touch_event(
    session: Session,
    event_id: str,
    *,
    last_seen: datetime,
    explanation: Optional[dict[str, Any]] = None,
    evidence: Optional[dict[str, Any]] = None,
    track_ids: Optional[list[str]] = None,
    observation_ids: Optional[list[str]] = None,
) -> Optional[m.EventRow]:
    row = session.get(m.EventRow, event_id)
    if row is None:
        return None
    row.last_seen = last_seen
    if explanation is not None:
        row.explanation = explanation
    if evidence is not None:
        row.evidence = evidence
    if track_ids is not None:
        row.track_ids = track_ids
    if observation_ids is not None:
        row.observation_ids = observation_ids
    session.flush()
    return row


def set_event_status(
    session: Session,
    row: m.EventRow,
    status: str,
    *,
    closed_reason: str = "",
) -> m.EventRow:
    row.status = status
    if closed_reason:
        row.closed_reason = closed_reason
    session.flush()
    return row


def list_events(
    session: Session,
    *,
    limit: int,
    offset: int,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    rule_id: Optional[str] = None,
    run_id: Optional[str] = None,
    source_id: Optional[str] = None,
    search: Optional[str] = None,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    sort: str = "created_at",
    order: str = "desc",
) -> tuple[list[m.EventRow], int]:
    stmt = select(m.EventRow)
    count_stmt = select(func.count(m.EventRow.event_id))
    conditions = []
    if severity:
        conditions.append(m.EventRow.severity == severity)
    if status:
        conditions.append(m.EventRow.status == status)
    if rule_id:
        conditions.append(m.EventRow.rule_id == rule_id)
    if run_id:
        conditions.append(m.EventRow.run_id == run_id)
    if source_id:
        conditions.append(m.EventRow.source_id == source_id)
    if since:
        conditions.append(m.EventRow.created_at >= since)
    if until:
        conditions.append(m.EventRow.created_at <= until)
    if search:
        like = f"%{search.lower()}%"
        conditions.append(
            func.lower(m.EventRow.title).like(like)
            | func.lower(m.EventRow.explanation.cast(type_=m.Text)).like(like)
        )
    for cond in conditions:
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)

    sort_col = {
        "created_at": m.EventRow.created_at,
        "severity": m.EventRow.severity,
        "last_seen": m.EventRow.last_seen,
        "status": m.EventRow.status,
    }.get(sort, m.EventRow.created_at)
    stmt = stmt.order_by(sort_col.asc() if order == "asc" else sort_col.desc())
    stmt = stmt.limit(limit).offset(offset)

    rows = list(session.scalars(stmt))
    total = session.scalar(count_stmt) or 0
    return rows, int(total)


def add_audit(
    session: Session,
    *,
    event_id: str,
    action: str,
    actor: str,
    note: str = "",
    timestamp: Optional[datetime] = None,
) -> m.EventAuditRow:
    row = m.EventAuditRow(
        audit_id=new_id("audit"),
        event_id=event_id,
        action=action,
        actor=actor,
        note=note,
        timestamp=timestamp or _now(),
    )
    session.add(row)
    session.flush()
    return row


def list_audit(session: Session, event_id: str) -> list[m.EventAuditRow]:
    return list(
        session.scalars(
            select(m.EventAuditRow)
            .where(m.EventAuditRow.event_id == event_id)
            .order_by(m.EventAuditRow.timestamp.asc())
        )
    )


def count_active_events(session: Session) -> int:
    return int(
        session.scalar(
            select(func.count(m.EventRow.event_id)).where(
                m.EventRow.status.in_(["active", "acknowledged"])
            )
        )
        or 0
    )


def count_events_in_window(
    session: Session, start: datetime, end: datetime, *, rule_id: Optional[str] = None
) -> int:
    stmt = select(func.count(m.EventRow.event_id)).where(
        m.EventRow.created_at >= start, m.EventRow.created_at <= end
    )
    if rule_id:
        stmt = stmt.where(m.EventRow.rule_id == rule_id)
    return int(session.scalar(stmt) or 0)


def group_events(
    session: Session, column: Any, start: datetime, end: datetime
) -> list[tuple[Any, int]]:
    stmt = (
        select(column, func.count(m.EventRow.event_id))
        .where(m.EventRow.created_at >= start, m.EventRow.created_at <= end)
        .group_by(column)
    )
    return [(row[0], int(row[1])) for row in session.execute(stmt)]


def events_in_window(
    session: Session, start: datetime, end: datetime
) -> list[m.EventRow]:
    return list(
        session.scalars(
            select(m.EventRow)
            .where(m.EventRow.created_at >= start, m.EventRow.created_at <= end)
            .order_by(m.EventRow.created_at.asc())
        )
    )


def latest_event(session: Session) -> Optional[m.EventRow]:
    return session.scalar(select(m.EventRow).order_by(m.EventRow.created_at.desc()).limit(1))


# --------------------------------------------------------------------------
# Evaluations
# --------------------------------------------------------------------------
def add_evaluation(
    session: Session,
    *,
    evaluation_id: str,
    rule_id: str,
    rule_version: int,
    run_id: str,
    observation_id: Optional[str],
    timestamp: datetime,
    outcome: str,
    payload: dict[str, Any],
    is_simulated: bool,
) -> None:
    session.add(
        m.EvaluationRow(
            evaluation_id=evaluation_id,
            rule_id=rule_id,
            rule_version=rule_version,
            run_id=run_id,
            observation_id=observation_id,
            timestamp=timestamp,
            outcome=outcome,
            payload=payload,
            is_simulated=is_simulated,
        )
    )


def list_evaluations(
    session: Session, *, rule_id: Optional[str] = None, limit: int = 100
) -> list[m.EvaluationRow]:
    stmt = select(m.EvaluationRow)
    if rule_id:
        stmt = stmt.where(m.EvaluationRow.rule_id == rule_id)
    stmt = stmt.order_by(m.EvaluationRow.timestamp.desc()).limit(limit)
    return list(session.scalars(stmt))


# --------------------------------------------------------------------------
# Evidence artifacts
# --------------------------------------------------------------------------
def list_artifacts(session: Session) -> list[m.EvidenceArtifactRow]:
    return list(session.scalars(select(m.EvidenceArtifactRow).order_by(m.EvidenceArtifactRow.type)))


def get_artifact(session: Session, artifact_id: str) -> Optional[m.EvidenceArtifactRow]:
    return session.get(m.EvidenceArtifactRow, artifact_id)


def upsert_artifact(
    session: Session,
    *,
    artifact_id: Optional[str],
    type_: str,
    label: str,
    path: str = "",
    status: str = "missing",
    required: bool = True,
    notes: str = "",
) -> m.EvidenceArtifactRow:
    row = session.get(m.EvidenceArtifactRow, artifact_id) if artifact_id else None
    if row is None:
        row = m.EvidenceArtifactRow(
            artifact_id=artifact_id or new_id("artifact"),
            type=type_,
            label=label,
            path=path,
            status=status,
            required=required,
            notes=notes,
        )
        session.add(row)
    else:
        row.type = type_
        row.label = label
        row.path = path
        row.status = status
        row.required = required
        row.notes = notes
    session.flush()
    return row


def verify_artifact(
    session: Session, artifact_id: str, *, status: str, notes: str = ""
) -> Optional[m.EvidenceArtifactRow]:
    row = session.get(m.EvidenceArtifactRow, artifact_id)
    if row is None:
        return None
    row.status = status
    if notes:
        row.notes = notes
    if status == "verified":
        row.verified_at = _now()
    session.flush()
    return row


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------
def record_metric(
    session: Session,
    *,
    name: str,
    value: float,
    unit: str = "",
    source: str = "measured",
    run_id: Optional[str] = None,
    is_valid: bool = True,
    measured_at: Optional[datetime] = None,
) -> None:
    session.add(
        m.MetricRow(
            run_id=run_id,
            name=name,
            value=value,
            unit=unit,
            source=source,
            is_valid=is_valid,
            measured_at=measured_at or _now(),
        )
    )


def recent_metrics(session: Session, name: str, limit: int = 100) -> list[m.MetricRow]:
    return list(
        session.scalars(
            select(m.MetricRow)
            .where(m.MetricRow.name == name)
            .order_by(m.MetricRow.measured_at.desc())
            .limit(limit)
        )
    )


# --------------------------------------------------------------------------
# App config key/value
# --------------------------------------------------------------------------
def get_config(session: Session, key: str) -> Optional[dict[str, Any]]:
    row = session.get(m.AppConfigRow, key)
    return row.value if row else None


def set_config(session: Session, key: str, value: dict[str, Any]) -> None:
    row = session.get(m.AppConfigRow, key)
    if row is None:
        row = m.AppConfigRow(key=key, value=value)
        session.add(row)
    else:
        row.value = value
        row.updated_at = _now()
    session.flush()


def reset_demo_data(session: Session) -> dict[str, int]:
    """Delete simulated runs, their events, and demo-seeded rules.

    Only removes records flagged ``is_simulated`` and seed rules. Never touches
    real-run data. Explicit, development-only invocation.
    """
    deleted = {"events": 0, "runs": 0, "rules": 0, "evaluations": 0}
    sim_events = list(session.scalars(select(m.EventRow).where(m.EventRow.is_simulated.is_(True))))
    for ev in sim_events:
        for audit in list(ev.audits):
            session.delete(audit)
        session.delete(ev)
    deleted["events"] = len(sim_events)

    sim_runs = list(session.scalars(select(m.RunRow).where(m.RunRow.is_simulated.is_(True))))
    for run in sim_runs:
        session.delete(run)
    deleted["runs"] = len(sim_runs)

    seed_rules = list(session.scalars(select(m.RuleRow).where(m.RuleRow.rule_id.like("rule_seed_%"))))
    for rule in seed_rules:
        for version in list(rule.versions):
            session.delete(version)
        session.delete(rule)
    deleted["rules"] = len(seed_rules)

    sim_evals = list(
        session.scalars(select(m.EvaluationRow).where(m.EvaluationRow.is_simulated.is_(True)))
    )
    for ev in sim_evals:
        session.delete(ev)
    deleted["evaluations"] = len(sim_evals)

    session.flush()
    return deleted
