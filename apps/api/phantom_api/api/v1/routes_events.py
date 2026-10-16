"""Event history, detail, status transitions, audit, and export."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse, Response
from sqlalchemy import select

from ...api.deps import context_from, transactional_session
from ...database import session_scope
from ... import db_models as m
from ...logging_config import get_logger
from ...repository import (
    add_audit,
    get_event,
    list_audit,
    list_events,
    set_event_status,
)
from ...schemas import EventAction, EventStatus, EventStatusUpdate

router = APIRouter(prefix="/events", tags=["events"])
logger = get_logger("phantom.api.events")

MAX_LIMIT = 200
VALID_SORTS = {"created_at", "severity", "last_seen", "status"}


def _serialize_event(row) -> dict:  # noqa: ANN001
    return {
        "schema_version": "1.0",
        "event_id": row.event_id,
        "run_id": row.run_id,
        "source_id": row.source_id,
        "rule_id": row.rule_id,
        "rule_version": row.rule_version,
        "created_at": row.created_at.isoformat(),
        "first_seen": row.first_seen.isoformat(),
        "last_seen": row.last_seen.isoformat(),
        "severity": row.severity,
        "status": row.status,
        "title": row.title,
        "provenance": row.provenance,
        "is_simulated": row.is_simulated,
        "correlation_id": row.correlation_id,
        "explanation": row.explanation,
        "evidence": row.evidence,
        "track_ids": row.track_ids,
        "observation_ids": row.observation_ids,
        "evidence_quality": row.evidence_quality,
        "closed_reason": row.closed_reason,
    }


@router.get("")
def get_events(
    request: Request,
    limit: int = Query(50, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
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
) -> dict:
    if sort not in VALID_SORTS:
        raise HTTPException(status_code=422, detail=f"sort must be one of {sorted(VALID_SORTS)}")
    if order not in ("asc", "desc"):
        raise HTTPException(status_code=422, detail="order must be 'asc' or 'desc'")
    with session_scope() as session:
        rows, total = list_events(
            session,
            limit=limit,
            offset=offset,
            severity=severity,
            status=status,
            rule_id=rule_id,
            run_id=run_id,
            source_id=source_id,
            search=search,
            since=since,
            until=until,
            sort=sort,
            order=order,
        )
    return {
        "items": [_serialize_event(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/export")
def export_events(
    request: Request,
    format: str = Query("json", pattern="^(json|csv)$"),
    status: Optional[str] = None,
    severity: Optional[str] = None,
    run_id: Optional[str] = None,
) -> Response:
    with session_scope() as session:
        rows, _ = list_events(
            session,
            limit=MAX_LIMIT * 50,
            offset=0,
            severity=severity,
            status=status,
            run_id=run_id,
        )
    records = [_serialize_event(r) for r in rows]
    if format == "json":
        body = json.dumps(
            {
                "schema_version": "1.0",
                "exported_at": datetime.now(tz=timezone.utc).isoformat(),
                "count": len(records),
                "items": records,
            },
            indent=2,
        )
        return Response(
            content=body,
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=phantom-events.json"},
        )
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "event_id",
            "run_id",
            "rule_id",
            "rule_version",
            "created_at",
            "last_seen",
            "severity",
            "status",
            "title",
            "is_simulated",
            "track_ids",
        ]
    )
    for r in records:
        writer.writerow(
            [
                r["event_id"],
                r["run_id"],
                r["rule_id"],
                r["rule_version"],
                r["created_at"],
                r["last_seen"],
                r["severity"],
                r["status"],
                r["title"],
                r["is_simulated"],
                ";".join(r["track_ids"] or []),
            ]
        )
    return PlainTextResponse(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=phantom-events.csv"},
    )


@router.get("/{event_id}")
def get_event_detail(request: Request, event_id: str) -> dict:
    with session_scope() as session:
        row = get_event(session, event_id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"Event '{event_id}' not found.")
        audits = list_audit(session, event_id)
    return {
        "event": _serialize_event(row),
        "audit": [
            {
                "audit_id": a.audit_id,
                "action": a.action,
                "actor": a.actor,
                "timestamp": a.timestamp.isoformat(),
                "note": a.note,
            }
            for a in audits
        ],
    }


@router.patch("/{event_id}")
def update_event_status(request: Request, event_id: str, body: EventStatusUpdate) -> dict:
    action_to_status = {
        "acknowledge": EventStatus.acknowledged,
        "resolve": EventStatus.resolved,
        "dismiss": EventStatus.dismissed,
        "reopen": EventStatus.active,
    }
    with transactional_session() as session:
        row = get_event(session, event_id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"Event '{event_id}' not found.")

        if body.action == "annotate":
            add_audit(
                session,
                event_id=event_id,
                action=EventAction.annotated.value,
                actor=body.actor,
                note=body.note,
            )
        else:
            target = action_to_status[body.action]
            if row.status == target.value:
                raise HTTPException(
                    status_code=409,
                    detail=f"Event is already '{target.value}'.",
                )
            set_event_status(
                session,
                row,
                target.value,
                closed_reason=body.note if target in (EventStatus.resolved, EventStatus.dismissed) else "",
            )
            add_audit(
                session,
                event_id=event_id,
                action=target.value,
                actor=body.actor,
                note=body.note,
            )
        session.flush()
        result_event = _serialize_event(row)
    return {"ok": True, "event": result_event}


@router.get("/{event_id}/audit")
def get_event_audit(request: Request, event_id: str) -> dict:
    with session_scope() as session:
        rows = list_audit(session, event_id)
    return {
        "items": [
            {
                "audit_id": a.audit_id,
                "event_id": a.event_id,
                "action": a.action,
                "actor": a.actor,
                "timestamp": a.timestamp.isoformat(),
                "note": a.note,
            }
            for a in rows
        ]
    }
