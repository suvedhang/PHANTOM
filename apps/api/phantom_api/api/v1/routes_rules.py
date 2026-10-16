"""Rule CRUD, versioning, and dry-run testing."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel
import json

from ...api.deps import context_from, transactional_session
from ...database import session_scope
from ...logging_config import get_logger
from ...repository import (
    create_rule as repo_create_rule,
    get_rule,
    get_rule_version,
    list_rules,
    update_rule as repo_update_rule,
)
from ...rule_engine.engine import RuleEngine, RuleValidationError
from ...schemas import (
    NormalizedEntity,
    Observation,
    Provenance,
    RuleCreate,
    RuleUpdate,
)
from ...services import rules_service

router = APIRouter(prefix="/rules", tags=["rules"])
logger = get_logger("phantom.api.rules")


def _serialize_rule(row) -> dict:  # noqa: ANN001
    return {
        "rule_id": row.rule_id,
        "name": row.name,
        "description": row.description,
        "type": row.type,
        "config": row.config,
        "severity": row.severity,
        "enabled": row.enabled,
        "version": row.version,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def _regions_map(session) -> dict:  # noqa: ANN001
    from ...repository import list_regions

    return rules_service.regions_by_id(list_regions(session))


@router.get("")
def get_rules(request: Request) -> dict:
    with session_scope() as session:
        rows = list_rules(session)
    return {"items": [_serialize_rule(r) for r in rows]}


@router.get("/export")
def export_rules(request: Request) -> Response:
    with session_scope() as session:
        rows = list_rules(session)
    body = json.dumps(
        {
            "schema_version": "1.0",
            "exported_at": datetime.now(tz=timezone.utc).isoformat(),
            "count": len(rows),
            "items": [_serialize_rule(r) for r in rows],
        },
        indent=2,
    )
    return Response(
        content=body,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=phantom-rules.json"},
    )


@router.post("", status_code=201)
def create_rule(request: Request, body: RuleCreate) -> dict:
    with transactional_session() as session:
        regions = _regions_map(session)
        domain_rule = rules_service.rule_row_to_definition  # for reference
        try:
            rules_service.ensure_supported_type(body.type)
        except RuleValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        # Validate region + required fields using a transient definition.
        from ...schemas import RuleDefinition

        transient = RuleDefinition(
            rule_id="transient",
            name=body.name,
            description=body.description,
            type=body.type,
            config=body.config,
            severity=body.severity,
            enabled=body.enabled,
        )
        try:
            rules_service.validate_rule_definition(transient, regions)
        except RuleValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        row = repo_create_rule(
            session,
            name=body.name,
            description=body.description,
            type_=body.type.value,
            config=body.config.model_dump(),
            severity=body.severity.value,
            enabled=body.enabled,
        )
        session.flush()
        payload = _serialize_rule(row)
    return payload


@router.get("/{rule_id}")
def get_single_rule(request: Request, rule_id: str) -> dict:
    with session_scope() as session:
        row = get_rule(session, rule_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found.")
    return _serialize_rule(row)


@router.get("/{rule_id}/versions")
def get_rule_versions(request: Request, rule_id: str) -> dict:
    with session_scope() as session:
        row = get_rule(session, rule_id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found.")
        versions = [
            {
                "version": v.version,
                "snapshot": v.snapshot,
                "created_at": v.created_at.isoformat(),
            }
            for v in sorted(row.versions, key=lambda v: v.version)
        ]
    return {"items": versions}


@router.get("/{rule_id}/versions/{version}")
def get_rule_version_detail(request: Request, rule_id: str, version: int) -> dict:
    with session_scope() as session:
        row = get_rule_version(session, rule_id, version)
    if row is None:
        raise HTTPException(status_code=404, detail="Rule version not found.")
    return {"version": row.version, "snapshot": row.snapshot, "created_at": row.created_at.isoformat()}


@router.put("/{rule_id}")
@router.patch("/{rule_id}")
def update_rule(request: Request, rule_id: str, body: RuleUpdate) -> dict:
    with transactional_session() as session:
        row = get_rule(session, rule_id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found.")
        regions = _regions_map(session)

        # Merge proposed changes onto the current definition for validation.
        merged = rules_service.rule_row_to_definition(row)
        if body.name is not None:
            merged.name = body.name
        if body.description is not None:
            merged.description = body.description
        if body.config is not None:
            merged.config = body.config
        if body.severity is not None:
            merged.severity = body.severity
        if body.enabled is not None:
            merged.enabled = body.enabled
        try:
            rules_service.validate_rule_definition(merged, regions)
        except RuleValidationError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        repo_update_rule(
            session,
            row,
            name=body.name,
            description=body.description,
            config=body.config.model_dump() if body.config is not None else None,
            severity=body.severity.value if body.severity is not None else None,
            enabled=body.enabled,
        )
        session.flush()
        payload = _serialize_rule(row)
    return payload


class RuleTestRequest(BaseModel):
    observations: list[Observation] = []
    # Optional inline events override; when omitted, observations are evaluated
    # in sequence against a fresh engine (dry run, nothing persisted).


@router.post("/{rule_id}/test")
def test_rule(request: Request, rule_id: str, body: RuleTestRequest) -> dict:
    with session_scope() as session:
        row = get_rule(session, rule_id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found.")
        regions = _regions_map(session)
        rule = rules_service.rule_row_to_definition(row)

    try:
        rules_service.validate_rule_definition(rule, regions)
    except RuleValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    engine = RuleEngine()
    evaluations: list[dict] = []
    would_trigger = 0
    for observation in body.observations:
        # Dry run: process into a throwaway engine; discard treatments so no
        # event is created and nothing is persisted.
        result = engine.process(observation, [rule], regions)
        for treatment in result.treatments:
            if treatment.kind == "create":
                would_trigger += 1
        evaluations.extend(e.model_dump(mode="json") for e in result.evaluations)

    return {
        "rule_id": rule_id,
        "rule_version": rule.version,
        "evaluated_observations": len(body.observations),
        "evaluation_count": len(evaluations),
        "would_trigger_count": would_trigger,
        "dry_run": True,
        "evaluations": evaluations,
        "note": "Dry run only. No events were created or persisted and no notifications were sent.",
    }


@router.post("/{rule_id}/sample-test")
def sample_test_rule(request: Request, rule_id: str) -> dict:
    """Run the rule against a small synthetic observation set derived from the
    demo scenario so operators can sanity-check a rule without a live source."""
    from ...demo.scenarios import workshop_scenario

    with session_scope() as session:
        row = get_rule(session, rule_id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"Rule '{rule_id}' not found.")
        regions = _regions_map(session)
        rule = rules_service.rule_row_to_definition(row)

    scenario = workshop_scenario()
    engine = RuleEngine()
    import uuid as _uuid

    triggered = 0
    evaluations: list[dict] = []
    for step in range(0, 30):
        t = float(step)
        entities = []
        for track in scenario.tracks:
            point = track.position_at(t)
            if point is None:
                continue
            from ...schemas import BoundingBox

            bbox = BoundingBox(
                x_min=max(0.0, point.x - 0.03),
                y_min=max(0.0, point.y - 0.07),
                x_max=min(1.0, point.x + 0.03),
                y_max=min(1.0, point.y + 0.07),
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
            observation_id=f"sample_{_uuid.uuid4().hex[:8]}",
            run_id="sample_run",
            source_id="sample",
            timestamp=datetime.now(tz=timezone.utc),
            frame_index=step,
            entities=entities,
            is_simulated=True,
        )
        result = engine.process(obs, [rule], regions)
        triggered += sum(1 for tr in result.treatments if tr.kind == "create")
        evaluations.extend(e.model_dump(mode="json") for e in result.evaluations)

    return {
        "rule_id": rule_id,
        "evaluated_observations": 30,
        "would_trigger_count": triggered,
        "dry_run": True,
        "evaluations": evaluations,
        "note": "Synthetic sample run (SIMULATED). Nothing was persisted or notified.",
    }
