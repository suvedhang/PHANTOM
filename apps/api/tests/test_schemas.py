"""Schema / contract tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from phantom_api.schemas import (
    BoundingBox,
    EventExplanation,
    EventStatus,
    IncidentEvent,
    NormalizedEntity,
    Observation,
    Polygon,
    Point,
    Provenance,
    Severity,
    SCHEMA_VERSION,
)


def test_observation_round_trip() -> None:
    o = Observation(
        observation_id="o1",
        run_id="r1",
        source_id="s1",
        timestamp=datetime.now(tz=timezone.utc),
        frame_index=1,
        entities=[
            NormalizedEntity(
                track_id="t1",
                class_label="person",
                bbox=BoundingBox(x_min=0.1, y_min=0.1, x_max=0.2, y_max=0.3),
                confidence=0.5,
            )
        ],
    )
    data = o.model_dump(mode="json")
    again = Observation.model_validate(data)
    assert again == o
    assert data["schema_version"] == SCHEMA_VERSION


def test_observation_requires_utc_timestamp() -> None:
    with pytest.raises(ValidationError):
        Observation(
            observation_id="o1",
            run_id="r1",
            source_id="s1",
            timestamp=datetime(2026, 1, 1),  # naive
            frame_index=0,
        )


def test_bounding_box_order_enforced() -> None:
    with pytest.raises(ValidationError):
        BoundingBox(x_min=0.5, y_min=0.5, x_max=0.2, y_max=0.9)


def test_bounding_box_out_of_range_rejected() -> None:
    with pytest.raises(ValidationError):
        BoundingBox(x_min=-0.1, y_min=0.0, x_max=0.2, y_max=0.9)


def test_polygon_min_points() -> None:
    with pytest.raises(ValidationError):
        Polygon(points=[Point(x=0.1, y=0.1), Point(x=0.2, y=0.2)])


def test_incident_event_round_trip() -> None:
    now = datetime.now(tz=timezone.utc)
    ev = IncidentEvent(
        event_id="evt_1",
        run_id="r1",
        source_id="s1",
        rule_id="rule1",
        rule_version=3,
        created_at=now,
        first_seen=now,
        last_seen=now,
        severity=Severity.high,
        status=EventStatus.active,
        title="Test",
        provenance=Provenance.derived,
        explanation=EventExplanation(human="h", machine={"condition": "x"}),
        track_ids=["t1"],
        observation_ids=["o1"],
    )
    data = ev.model_dump(mode="json")
    again = IncidentEvent.model_validate(data)
    assert again == ev
    assert data["schema_version"] == SCHEMA_VERSION
    assert data["rule_version"] == 3


def test_status_update_requires_note_for_dismiss() -> None:
    from phantom_api.schemas import EventStatusUpdate

    with pytest.raises(ValidationError):
        EventStatusUpdate(action="dismiss")
    # annotate also requires a note
    with pytest.raises(ValidationError):
        EventStatusUpdate(action="annotate")
    ok = EventStatusUpdate(action="dismiss", note="Not a real incident.")
    assert ok.note == "Not a real incident."


def test_confidence_is_bounded() -> None:
    with pytest.raises(ValidationError):
        NormalizedEntity(class_label="person", confidence=1.5)
