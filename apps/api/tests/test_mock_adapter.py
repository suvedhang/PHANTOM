"""Mock adapter tests: determinism and SIMULATED labelling."""

from __future__ import annotations

from datetime import datetime, timezone

from phantom_api.adapters.mock import MockPipelineAdapter
from phantom_api.demo.scenarios import workshop_scenario
from phantom_api.rule_engine.engine import RuleEngine
from phantom_api.schemas import Provenance, RuleConfig, RuleDefinition, RuleType, Severity
from tests.test_rule_engine import REGIONS


def test_observations_are_labelled_simulated() -> None:
    adapter = MockPipelineAdapter(start_time=datetime.now(tz=timezone.utc))
    o = adapter.build_observation(3.0)
    assert o.is_simulated is True
    assert o.entities
    assert all(e.provenance == Provenance.simulated for e in o.entities)


def test_positions_are_deterministic() -> None:
    fixed = datetime(2026, 1, 1, tzinfo=timezone.utc)
    a = MockPipelineAdapter(start_time=fixed).build_observation(2.5)
    b = MockPipelineAdapter(start_time=fixed).build_observation(2.5)
    a_points = [(e.track_id, e.bbox) for e in a.entities]
    b_points = [(e.track_id, e.bbox) for e in b.entities]
    assert a_points == b_points


def test_scenario_interpolation_bounds() -> None:
    scenario = workshop_scenario()
    for track in scenario.tracks:
        assert track.position_at(track.start_time - 1) is None
        assert track.position_at(track.end_time + 1) is None
        mid = track.position_at((track.start_time + track.end_time) / 2)
        assert mid is not None


def _rules() -> list[RuleDefinition]:
    return [
        RuleDefinition(
            rule_id="rule_seed_restricted_entry",
            name="entry",
            type=RuleType.region_entry,
            config=RuleConfig(region_id="r1", class_filter=[]),
            severity=Severity.high,
        ),
        RuleDefinition(
            rule_id="rule_seed_dwell",
            name="dwell",
            type=RuleType.dwell_time,
            config=RuleConfig(region_id="r1", dwell_seconds=5.0),
            severity=Severity.medium,
        ),
        RuleDefinition(
            rule_id="rule_seed_wrongway",
            name="wrongway",
            type=RuleType.wrong_way,
            config=RuleConfig(
                class_filter=["person"], allowed_direction_deg=0.0, min_displacement=0.15
            ),
            severity=Severity.high,
        ),
    ]


def test_scenario_drives_all_three_rule_types() -> None:
    """The scripted scenario must trigger region entry, dwell, and wrong-way."""
    engine = RuleEngine(stale_track_seconds=10000)
    adapter = MockPipelineAdapter(start_time=datetime(2026, 1, 1, tzinfo=timezone.utc))
    triggered_types = set()
    for step in range(0, 15 * 16):
        o = adapter.build_observation(step / 15.0)
        result = engine.process(o, _rules(), REGIONS)
        for treatment in result.treatments:
            if treatment.kind == "create":
                triggered_types.add(treatment.rule.type)
    assert RuleType.region_entry in triggered_types
    assert RuleType.dwell_time in triggered_types
    assert RuleType.wrong_way in triggered_types
