"""Unit tests for the deterministic rule engine."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from phantom_api.rule_engine.engine import (
    RuleEngine,
    RuleValidationError,
    validate_rule,
)
from phantom_api.schemas import (
    BoundingBox,
    NormalizedEntity,
    Observation,
    Point,
    Polygon,
    Provenance,
    RuleConfig,
    RuleDefinition,
    RuleType,
    Severity,
)

BASE = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def poly() -> Polygon:
    return Polygon(
        points=[
            Point(x=0.2, y=0.2),
            Point(x=0.8, y=0.2),
            Point(x=0.8, y=0.8),
            Point(x=0.2, y=0.8),
        ]
    )


REGIONS = {"r1": poly()}


def obs(frame: int, entities: list[tuple[str, str, float, float]], *, sim: bool = False, seconds: float | None = None) -> Observation:
    ts = BASE + timedelta(seconds=seconds if seconds is not None else frame)
    normalized = []
    for track_id, cls, x, y in entities:
        normalized.append(
            NormalizedEntity(
                track_id=track_id or None,
                class_label=cls,
                bbox=BoundingBox(
                    x_min=max(0.0, x - 0.03),
                    y_min=max(0.0, y - 0.03),
                    x_max=min(1.0, x + 0.03),
                    y_max=min(1.0, y + 0.03),
                ),
                confidence=0.9,
                provenance=Provenance.simulated if sim else Provenance.observed,
            )
        )
    return Observation(
        observation_id=f"o{frame}",
        run_id="run1",
        source_id="src",
        timestamp=ts,
        frame_index=frame,
        entities=normalized,
        is_simulated=sim,
    )


def make_rule(rule_type: RuleType, config: RuleConfig, **kwargs) -> RuleDefinition:
    return RuleDefinition(
        rule_id=f"rule_{rule_type.value}",
        name=rule_type.value,
        type=rule_type,
        config=config,
        severity=kwargs.get("severity", Severity.medium),
        version=kwargs.get("version", 1),
        enabled=kwargs.get("enabled", True),
    )


def fresh_engine() -> RuleEngine:
    return RuleEngine(stale_track_seconds=10_000)


# --------------------------------------------------------------------------
# Region entry
# --------------------------------------------------------------------------
def test_region_entry_outside_no_trigger() -> None:
    engine = fresh_engine()
    rule = make_rule(RuleType.region_entry, RuleConfig(region_id="r1"))
    result = engine.process(obs(0, [("t1", "person", 0.1, 0.1)]), [rule], REGIONS)
    assert result.treatments == []


def test_region_entry_inside_creates_then_stays_active() -> None:
    engine = fresh_engine()
    rule = make_rule(RuleType.region_entry, RuleConfig(region_id="r1"))
    r0 = engine.process(obs(0, [("t1", "person", 0.1, 0.1)]), [rule], REGIONS)
    assert not r0.treatments
    r1 = engine.process(obs(1, [("t1", "person", 0.5, 0.5)]), [rule], REGIONS)
    assert [t.kind for t in r1.treatments] == ["create"]
    engine.set_event_id("rule_region_entry:t1", "evt_1")
    # Continues inside: no new create, no clear.
    r2 = engine.process(obs(2, [("t1", "person", 0.55, 0.5)]), [rule], REGIONS)
    assert all(t.kind != "create" for t in r2.treatments)
    assert all(t.kind != "clear" for t in r2.treatments)
    # Leaves: clear.
    r3 = engine.process(obs(3, [("t1", "person", 0.05, 0.9)]), [rule], REGIONS)
    assert [t.kind for t in r3.treatments] == ["clear"]


def test_region_entry_boundary_point_counts_as_inside() -> None:
    engine = fresh_engine()
    rule = make_rule(RuleType.region_entry, RuleConfig(region_id="r1"))
    result = engine.process(obs(0, [("t1", "person", 0.2, 0.5)]), [rule], REGIONS)
    assert [t.kind for t in result.treatments] == ["create"]


def test_region_entry_disabled_rule_not_evaluated() -> None:
    engine = fresh_engine()
    rule = make_rule(RuleType.region_entry, RuleConfig(region_id="r1"), enabled=False)
    result = engine.process(obs(0, [("t1", "person", 0.5, 0.5)]), [rule], REGIONS)
    assert result.treatments == []


def test_region_entry_class_filter() -> None:
    engine = fresh_engine()
    rule = make_rule(RuleType.region_entry, RuleConfig(region_id="r1", class_filter=["car"]))
    result = engine.process(obs(0, [("t1", "person", 0.5, 0.5)]), [rule], REGIONS)
    assert result.treatments == []


def test_region_entry_missing_bbox_is_ignored() -> None:
    engine = fresh_engine()
    rule = make_rule(RuleType.region_entry, RuleConfig(region_id="r1"))
    o = Observation(
        observation_id="o0",
        run_id="r",
        source_id="s",
        timestamp=BASE,
        frame_index=0,
        entities=[NormalizedEntity(track_id="t1", class_label="person", bbox=None)],
    )
    result = engine.process(o, [rule], REGIONS)
    assert result.treatments == []


# --------------------------------------------------------------------------
# Dwell
# --------------------------------------------------------------------------
def test_dwell_below_threshold() -> None:
    engine = fresh_engine()
    rule = make_rule(RuleType.dwell_time, RuleConfig(region_id="r1", dwell_seconds=5.0))
    engine.process(obs(0, [("t1", "person", 0.5, 0.5)], seconds=0), [rule], REGIONS)
    result = engine.process(obs(1, [("t1", "person", 0.5, 0.5)], seconds=3), [rule], REGIONS)
    assert result.treatments == []


def test_dwell_at_threshold_triggers() -> None:
    engine = fresh_engine()
    rule = make_rule(RuleType.dwell_time, RuleConfig(region_id="r1", dwell_seconds=5.0))
    engine.process(obs(0, [("t1", "person", 0.5, 0.5)], seconds=0), [rule], REGIONS)
    result = engine.process(obs(1, [("t1", "person", 0.5, 0.5)], seconds=5), [rule], REGIONS)
    assert [t.kind for t in result.treatments] == ["create"]


def test_dwell_above_threshold_triggers_once() -> None:
    engine = fresh_engine()
    rule = make_rule(RuleType.dwell_time, RuleConfig(region_id="r1", dwell_seconds=5.0, dedup_seconds=100))
    engine.process(obs(0, [("t1", "person", 0.5, 0.5)], seconds=0), [rule], REGIONS)
    r1 = engine.process(obs(1, [("t1", "person", 0.5, 0.5)], seconds=6), [rule], REGIONS)
    r2 = engine.process(obs(2, [("t1", "person", 0.5, 0.5)], seconds=7), [rule], REGIONS)
    assert [t.kind for t in r1.treatments] == ["create"]
    assert not any(t.kind == "create" for t in r2.treatments)


def test_dwell_track_leaving_clears() -> None:
    engine = fresh_engine()
    rule = make_rule(RuleType.dwell_time, RuleConfig(region_id="r1", dwell_seconds=2.0))
    engine.process(obs(0, [("t1", "person", 0.5, 0.5)], seconds=0), [rule], REGIONS)
    engine.process(obs(1, [("t1", "person", 0.5, 0.5)], seconds=3), [rule], REGIONS)
    engine.set_event_id("rule_dwell_time:t1", "evt_dwell")
    result = engine.process(obs(2, [("t1", "person", 0.05, 0.05)], seconds=4), [rule], REGIONS)
    assert [t.kind for t in result.treatments] == ["clear"]


# --------------------------------------------------------------------------
# Wrong way
# --------------------------------------------------------------------------
def test_wrong_way_allowed_direction_no_trigger() -> None:
    engine = fresh_engine()
    rule = make_rule(
        RuleType.wrong_way, RuleConfig(allowed_direction_deg=0.0, min_displacement=0.1)
    )
    engine.process(obs(0, [("t1", "person", 0.1, 0.5)]), [rule], REGIONS)
    result = engine.process(obs(1, [("t1", "person", 0.9, 0.5)]), [rule], REGIONS)
    assert result.treatments == []


def test_wrong_way_opposite_direction_triggers() -> None:
    engine = fresh_engine()
    rule = make_rule(RuleType.wrong_way, RuleConfig(allowed_direction_deg=0.0, min_displacement=0.2))
    engine.process(obs(0, [("t1", "person", 0.9, 0.5)]), [rule], REGIONS)
    result = engine.process(obs(1, [("t1", "person", 0.1, 0.5)]), [rule], REGIONS)
    assert [t.kind for t in result.treatments] == ["create"]


def test_wrong_way_stationary_no_trigger() -> None:
    engine = fresh_engine()
    rule = make_rule(RuleType.wrong_way, RuleConfig(allowed_direction_deg=0.0, min_displacement=0.05))
    engine.process(obs(0, [("t1", "person", 0.5, 0.5)]), [rule], REGIONS)
    result = engine.process(obs(1, [("t1", "person", 0.5, 0.5)]), [rule], REGIONS)
    assert result.treatments == []


def test_wrong_way_insufficient_history_no_trigger() -> None:
    engine = fresh_engine()
    rule = make_rule(RuleType.wrong_way, RuleConfig(allowed_direction_deg=0.0, min_displacement=0.1))
    result = engine.process(obs(0, [("t1", "person", 0.9, 0.5)]), [rule], REGIONS)
    assert result.treatments == []


def test_wrong_way_missing_track_id_is_ignored() -> None:
    engine = fresh_engine()
    rule = make_rule(RuleType.wrong_way, RuleConfig(allowed_direction_deg=0.0, min_displacement=0.1))
    engine.process(obs(0, [("", "person", 0.9, 0.5)]), [rule], REGIONS)
    result = engine.process(obs(1, [("", "person", 0.1, 0.5)]), [rule], REGIONS)
    assert result.treatments == []


# --------------------------------------------------------------------------
# Count threshold
# --------------------------------------------------------------------------
def test_count_below_threshold() -> None:
    engine = fresh_engine()
    rule = make_rule(RuleType.count_threshold, RuleConfig(region_id="r1", count_threshold=3, sustain_seconds=1.0))
    result = engine.process(obs(0, [("t1", "person", 0.5, 0.5), ("t2", "person", 0.5, 0.5)], seconds=0), [rule], REGIONS)
    assert result.treatments == []


def test_count_threshold_sustained_triggers() -> None:
    engine = fresh_engine()
    rule = make_rule(RuleType.count_threshold, RuleConfig(region_id="r1", count_threshold=2, sustain_seconds=1.0))
    entities = [("t1", "person", 0.5, 0.5), ("t2", "person", 0.55, 0.55), ("t3", "person", 0.6, 0.6)]
    engine.process(obs(0, entities, seconds=0), [rule], REGIONS)
    result = engine.process(obs(1, entities, seconds=2), [rule], REGIONS)
    assert [t.kind for t in result.treatments] == ["create"]


def test_count_duplicate_track_ids_counted_once() -> None:
    engine = fresh_engine()
    rule = make_rule(RuleType.count_threshold, RuleConfig(region_id="r1", count_threshold=2, sustain_seconds=1.0))
    # Same track id twice in a frame should count once (region membership is per track).
    entities = [("t1", "person", 0.5, 0.5), ("t1", "person", 0.5, 0.5)]
    engine.process(obs(0, entities, seconds=0), [rule], REGIONS)
    result = engine.process(obs(1, entities, seconds=2), [rule], REGIONS)
    assert result.treatments == []


# --------------------------------------------------------------------------
# Cooldown / dedup
# --------------------------------------------------------------------------
def test_cooldown_suppresses_retrigger() -> None:
    engine = fresh_engine()
    rule = make_rule(RuleType.region_entry, RuleConfig(region_id="r1", cooldown_seconds=5.0))
    engine.process(obs(0, [("t1", "person", 0.5, 0.5)], seconds=0), [rule], REGIONS)
    engine.process(obs(1, [("t1", "person", 0.1, 0.1)], seconds=1), [rule], REGIONS)  # clear at t=1
    r2 = engine.process(obs(2, [("t1", "person", 0.5, 0.5)], seconds=2), [rule], REGIONS)
    assert not any(t.kind == "create" for t in r2.treatments)
    # After cooldown elapses it may trigger again.
    result = engine.process(obs(3, [("t1", "person", 0.5, 0.5)], seconds=10), [rule], REGIONS)
    assert [t.kind for t in result.treatments][0] == "create"


def test_dedup_suppresses_redundant_updates() -> None:
    engine = fresh_engine()
    rule = make_rule(RuleType.region_entry, RuleConfig(region_id="r1", dedup_seconds=100.0))
    engine.process(obs(0, [("t1", "person", 0.5, 0.5)], seconds=0), [rule], REGIONS)
    r1 = engine.process(obs(1, [("t1", "person", 0.5, 0.5)], seconds=1), [rule], REGIONS)
    r2 = engine.process(obs(2, [("t1", "person", 0.5, 0.5)], seconds=2), [rule], REGIONS)
    # A persistent condition must not re-create the event; updates are throttled.
    assert not any(t.kind == "create" for t in r1.treatments + r2.treatments)
    assert r2.treatments == []
    assert all(t.kind == "update" for t in r1.treatments)


def test_persistent_violation_does_not_create_every_frame() -> None:
    engine = fresh_engine()
    rule = make_rule(RuleType.region_entry, RuleConfig(region_id="r1", dedup_seconds=100))
    creates = 0
    for i in range(10):
        result = engine.process(obs(i, [("t1", "person", 0.5, 0.5)]), [rule], REGIONS)
        creates += sum(1 for t in result.treatments if t.kind == "create")
    assert creates == 1


# --------------------------------------------------------------------------
# Region exit
# --------------------------------------------------------------------------
def test_region_exit_triggers_on_leaving() -> None:
    engine = fresh_engine()
    rule = make_rule(RuleType.region_exit, RuleConfig(region_id="r1"))
    engine.process(obs(0, [("t1", "person", 0.5, 0.5)]), [rule], REGIONS)
    result = engine.process(obs(1, [("t1", "person", 0.1, 0.1)]), [rule], REGIONS)
    assert [t.kind for t in result.treatments] == ["create"]


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------
def test_validate_unsupported_type() -> None:
    rule = make_rule(RuleType.sequence, RuleConfig())
    with pytest.raises(RuleValidationError):
        validate_rule(rule, REGIONS)


def test_validate_missing_region() -> None:
    rule = make_rule(RuleType.region_entry, RuleConfig(region_id="missing"))
    with pytest.raises(RuleValidationError):
        validate_rule(rule, REGIONS)


def test_validate_dwell_requires_duration() -> None:
    rule = make_rule(RuleType.dwell_time, RuleConfig(region_id="r1"))
    with pytest.raises(RuleValidationError):
        validate_rule(rule, REGIONS)


def test_validate_wrong_way_requires_direction() -> None:
    rule = make_rule(RuleType.wrong_way, RuleConfig())
    with pytest.raises(RuleValidationError):
        validate_rule(rule, REGIONS)


def test_simulated_provenance_flows_into_treatment() -> None:
    engine = fresh_engine()
    rule = make_rule(RuleType.region_entry, RuleConfig(region_id="r1"))
    result = engine.process(obs(0, [("t1", "person", 0.5, 0.5)], sim=True), [rule], REGIONS)
    assert result.treatments[0].provenance == Provenance.simulated
