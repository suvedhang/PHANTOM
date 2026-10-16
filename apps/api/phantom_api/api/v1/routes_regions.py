"""Region CRUD (normalized polygon regions)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from ...api.deps import transactional_session
from ...database import session_scope
from ...logging_config import get_logger
from ...repository import (
    delete_region,
    get_region,
    list_regions,
    list_rules,
    upsert_region,
)
from ...schemas import RegionCreate
from ...services import rules_service

router = APIRouter(prefix="/regions", tags=["regions"])
logger = get_logger("phantom.api.regions")


def _serialize(row) -> dict:  # noqa: ANN001
    return {
        "region_id": row.region_id,
        "name": row.name,
        "polygon": row.polygon,
        "enabled": row.enabled,
        "version": row.version,
    }


@router.get("")
def get_regions(request: Request) -> dict:
    with session_scope() as session:
        rows = list_regions(session)
    return {"items": [_serialize(r) for r in rows]}


@router.post("", status_code=201)
def create_or_update_region(request: Request, body: RegionCreate) -> dict:
    with transactional_session() as session:
        row = upsert_region(
            session,
            region_id=body.region_id,
            name=body.name,
            polygon=[p.model_dump() for p in body.polygon.points],
            enabled=body.enabled,
        )
        session.flush()
        payload = _serialize(row)
    return payload


@router.put("/{region_id}")
def update_region(request: Request, region_id: str, body: RegionCreate) -> dict:
    with transactional_session() as session:
        if get_region(session, region_id) is None:
            raise HTTPException(status_code=404, detail=f"Region '{region_id}' not found.")
        row = upsert_region(
            session,
            region_id=region_id,
            name=body.name,
            polygon=[p.model_dump() for p in body.polygon.points],
            enabled=body.enabled,
        )
        session.flush()
        payload = _serialize(row)
    return payload


@router.delete("/{region_id}")
def remove_region(request: Request, region_id: str) -> dict:
    with transactional_session() as session:
        if get_region(session, region_id) is None:
            raise HTTPException(status_code=404, detail=f"Region '{region_id}' not found.")
        referencing = [
            r.rule_id for r in list_rules(session) if r.config.get("region_id") == region_id
        ]
        if referencing:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Region '{region_id}' is referenced by rules: {', '.join(referencing)}. "
                    "Update or delete those rules first."
                ),
            )
        delete_region(session, region_id)
    return {"ok": True, "deleted": region_id}
