"""Evidence registry endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ...api.deps import transactional_session
from ...database import session_scope
from ...repository import get_artifact, upsert_artifact, verify_artifact
from ...services import evidence

router = APIRouter(prefix="/evidence", tags=["evidence"])


class ArtifactUpdate(BaseModel):
    path: str = ""
    status: str = "pending"
    notes: str = ""


@router.get("/status")
def evidence_status(request: Request) -> dict:
    with session_scope() as session:
        return evidence.status_summary(session)


@router.put("/{artifact_id}")
def update_artifact(request: Request, artifact_id: str, body: ArtifactUpdate) -> dict:
    with transactional_session() as session:
        row = get_artifact(session, artifact_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Artifact not found.")
        row.path = body.path
        row.status = body.status
        row.notes = body.notes
        session.flush()
        payload = {
            "artifact_id": row.artifact_id,
            "status": row.status,
            "path": row.path,
            "notes": row.notes,
        }
    return payload


class ArtifactVerify(BaseModel):
    status: str = "verified"
    notes: str = ""


@router.post("/{artifact_id}/verify")
def verify(request: Request, artifact_id: str, body: ArtifactVerify) -> dict:
    if body.status not in ("verified", "invalid", "captured", "pending", "missing"):
        raise HTTPException(status_code=422, detail="Invalid evidence status.")
    with transactional_session() as session:
        row = verify_artifact(session, artifact_id, status=body.status, notes=body.notes)
        if row is None:
            raise HTTPException(status_code=404, detail="Artifact not found.")
        payload = {
            "artifact_id": row.artifact_id,
            "status": row.status,
            "verified_at": row.verified_at.isoformat() if row.verified_at else None,
            "notes": row.notes,
        }
    return payload
