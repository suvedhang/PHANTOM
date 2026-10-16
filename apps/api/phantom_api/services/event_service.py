"""Event service: turns rule-engine treatments into persisted, auditable events.

Responsibilities:
* build a deterministic, versioned :class:`IncidentEvent` from a treatment;
* persist it (and audit entries) via the repository;
* broadcast it over WebSocket and (optionally) MQTT.

It contains no HTTP concerns and is unit-testable with an in-memory database.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from .. import repository as repo
from ..logging_config import get_logger
from ..rule_engine.engine import Treatment
from ..schemas import EventExplanation, IncidentEvent, Provenance
from . import rules_service

logger = get_logger("phantom.events")


def _new_event_id(is_simulated: bool) -> str:
    prefix = "evt_sim" if is_simulated else "evt"
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


class EventService:
    def __init__(self, hub, mqtt) -> None:  # noqa: ANN001 - loose coupling for tests
        self._hub = hub
        self._mqtt = mqtt

    async def handle_treatment(
        self,
        session: Session,
        treatment: Treatment,
        engine,  # noqa: ANN001
        *,
        run_id: str,
        source_id: str,
        correlation_id: Optional[str],
    ) -> Optional[IncidentEvent]:
        if treatment.kind == "create":
            return await self._create(
                session, treatment, engine, run_id, source_id, correlation_id
            )
        if treatment.kind == "update":
            return await self._update(session, treatment, run_id, source_id)
        if treatment.kind == "clear":
            return await self._clear(session, treatment)
        return None

    # -- create ---------------------------------------------------------
    async def _create(
        self,
        session: Session,
        treatment: Treatment,
        engine,  # noqa: ANN001
        run_id: str,
        source_id: str,
        correlation_id: Optional[str],
    ) -> IncidentEvent:
        event_id = _new_event_id(treatment.provenance is Provenance.simulated)
        explanation = EventExplanation(
            human=treatment.human,
            machine=treatment.machine,
        )
        evidence = {
            "observed": treatment.machine.get("observed", {}),
            "threshold": treatment.machine.get("threshold", {}),
            "rule_type": treatment.rule.type.value,
            "condition": treatment.machine.get("condition"),
            "observation_id": treatment.observation_id,
        }
        event = IncidentEvent(
            event_id=event_id,
            run_id=run_id,
            source_id=source_id,
            rule_id=treatment.rule.rule_id,
            rule_version=treatment.rule.version,
            created_at=treatment.timestamp,
            first_seen=treatment.timestamp,
            last_seen=treatment.timestamp,
            severity=treatment.severity,
            title=treatment.title,
            provenance=treatment.provenance,
            is_simulated=treatment.provenance is Provenance.simulated,
            correlation_id=correlation_id,
            explanation=explanation,
            evidence=evidence,
            track_ids=treatment.track_ids,
            observation_ids=[treatment.observation_id],
            evidence_quality=treatment.evidence_quality,
        )
        repo.create_event(session, event, dedup_key=treatment.dedup_key)
        repo.add_audit(
            session,
            event_id=event_id,
            action="created",
            actor="system",
            note=treatment.human,
            timestamp=treatment.timestamp,
        )
        engine.set_event_id(treatment.dedup_key, event_id)
        logger.info(
            "event created",
            extra={"component": "events", "event_id": event_id, "run_id": run_id},
        )
        await self._broadcast("event_created", self._serialize(event))
        return event

    # -- update ---------------------------------------------------------
    async def _update(
        self,
        session: Session,
        treatment: Treatment,
        run_id: str,
        source_id: str,
    ) -> Optional[IncidentEvent]:
        if treatment.event_id is None:
            return None
        row = repo.touch_event(
            session,
            treatment.event_id,
            last_seen=treatment.timestamp,
            explanation=EventExplanation(
                human=treatment.human, machine=treatment.machine
            ).model_dump(mode="json"),
            evidence={
                "observed": treatment.machine.get("observed", {}),
                "threshold": treatment.machine.get("threshold", {}),
                "rule_type": treatment.rule.type.value,
                "condition": treatment.machine.get("condition"),
                "observation_id": treatment.observation_id,
            },
            track_ids=treatment.track_ids,
        )
        if row is None:
            return None
        event = _row_to_model(row)
        await self._broadcast("event_updated", self._serialize(event))
        return event

    # -- clear ----------------------------------------------------------
    async def _clear(
        self, session: Session, treatment: Treatment
    ) -> Optional[IncidentEvent]:
        if treatment.event_id is None:
            return None
        row = repo.get_event(session, treatment.event_id)
        if row is None:
            return None
        if row.status in ("active", "acknowledged"):
            repo.set_event_status(session, row, "resolved", closed_reason="condition_cleared")
            repo.add_audit(
                session,
                event_id=row.event_id,
                action="cleared",
                actor="system",
                note="Violation condition cleared automatically.",
                timestamp=treatment.timestamp,
            )
        event = _row_to_model(row)
        await self._broadcast("event_updated", self._serialize(event))
        return event

    # -- helpers --------------------------------------------------------
    async def _broadcast(self, message_type: str, payload: dict) -> None:
        if self._hub is not None:
            await self._hub.broadcast(message_type, payload)
        if self._mqtt is not None:
            channel = "events" if message_type.startswith("event") else "status"
            self._mqtt.publish(channel, {"type": message_type, **payload})

    @staticmethod
    def _serialize(event: IncidentEvent) -> dict:
        return event.model_dump(mode="json")


def _row_to_model(row) -> IncidentEvent:  # noqa: ANN001
    from ..schemas import EventStatus, EventExplanation  # local import to avoid cycle

    return IncidentEvent(
        event_id=row.event_id,
        run_id=row.run_id,
        source_id=row.source_id,
        rule_id=row.rule_id,
        rule_version=row.rule_version,
        created_at=row.created_at,
        first_seen=row.first_seen,
        last_seen=row.last_seen,
        severity=row.severity,
        status=EventStatus(row.status),
        title=row.title,
        provenance=Provenance(row.provenance),
        is_simulated=row.is_simulated,
        correlation_id=row.correlation_id,
        explanation=EventExplanation(**row.explanation),
        evidence=row.evidence,
        track_ids=row.track_ids,
        observation_ids=row.observation_ids,
        evidence_quality=row.evidence_quality,
    )


__all__ = ["EventService", "_row_to_model"]
