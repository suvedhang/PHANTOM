"""Deterministic scene-specific rule engine.

The engine consumes normalized :class:`Observation` objects frame by frame,
maintains bounded track history and per-rule violation state, and emits
deterministic evaluations plus event transitions. It contains no FastAPI or
database concerns so it can be unit tested in isolation.

Design notes
------------
* Active violations are keyed by a stable ``dedup_key`` so a persistent
  condition does not create a new event every frame.
* Cooldown suppresses re-triggering of the *same* dedup key shortly after it
  clears; dedup suppresses redundant ``update`` emissions while active.
* Track history is bounded. Stale tracks expire according to a documented
  policy (``stale_track_seconds``).
"""

from __future__ import annotations

import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal, Optional

from ..schemas import (
    BoundingBox,
    Observation,
    Polygon,
    Provenance,
    RuleDefinition,
    RuleEvaluation,
    EvaluationOutcome,
    RuleType,
    SCHEMA_VERSION,
    Severity,
    Point,
)
from .geometry import (
    angular_difference_degrees,
    bearing_degrees,
    displacement,
    point_in_polygon,
)

SUPPORTED_RULE_TYPES: frozenset[RuleType] = frozenset(
    {
        RuleType.region_entry,
        RuleType.region_exit,
        RuleType.dwell_time,
        RuleType.wrong_way,
        RuleType.count_threshold,
    }
)

# A track is "wrong way" only when its image-space bearing is within
# (180 - WRONG_WAY_TOLERANCE_DEG) degrees of the exact opposite of the allowed
# direction, i.e. clearly heading back. Documented, tested threshold.
WRONG_WAY_TOLERANCE_DEG = 30.0

HISTORY_LENGTH = 60
DEFAULT_STALE_TRACK_SECONDS = 4.0


class RuleValidationError(ValueError):
    """Raised when a rule configuration is invalid or unsupported."""


def validate_rule(rule: RuleDefinition, regions: dict[str, Polygon]) -> None:
    """Validate a rule against the supported types and available regions.

    Raises :class:`RuleValidationError` with a human-readable message.
    """
    rtype = rule.type
    if rtype not in SUPPORTED_RULE_TYPES:
        supported = ", ".join(sorted(t.value for t in SUPPORTED_RULE_TYPES))
        raise RuleValidationError(
            f"Rule type '{rtype.value}' is not supported by the deterministic engine. "
            f"Supported types: {supported}."
        )

    needs_region = {
        RuleType.region_entry,
        RuleType.region_exit,
        RuleType.dwell_time,
        RuleType.count_threshold,
    }
    if rtype in needs_region:
        if not rule.config.region_id:
            raise RuleValidationError(f"{rtype.value} requires a region_id.")
        if rule.config.region_id not in regions:
            raise RuleValidationError(
                f"Region '{rule.config.region_id}' does not exist for rule '{rule.rule_id}'."
            )

    if rtype == RuleType.dwell_time and not rule.config.dwell_seconds:
        raise RuleValidationError("dwell_time requires dwell_seconds > 0.")

    if rtype == RuleType.count_threshold:
        if not rule.config.count_threshold:
            raise RuleValidationError("count_threshold requires count_threshold > 0.")
        if not rule.config.sustain_seconds:
            raise RuleValidationError("count_threshold requires sustain_seconds > 0.")

    if rtype == RuleType.wrong_way:
        if rule.config.allowed_direction_deg is None:
            raise RuleValidationError("wrong_way requires allowed_direction_deg.")
        if rule.config.min_displacement is None:
            raise RuleValidationError("wrong_way requires min_displacement > 0.")


@dataclass
class TrackState:
    track_id: str
    class_label: str
    first_seen: datetime
    last_seen: datetime
    positions: deque[tuple[datetime, Point]] = field(default_factory=deque)
    best_confidence: Optional[float] = None

    def point(self) -> Optional[Point]:
        return self.positions[-1][1] if self.positions else None


@dataclass
class ActiveViolation:
    dedup_key: str
    rule_id: str
    rule_version: int
    first_seen: datetime
    last_seen: datetime
    event_id: Optional[str] = None
    last_update_emitted: Optional[datetime] = None
    track_ids: list[str] = field(default_factory=list)
    observation_ids: list[str] = field(default_factory=list)


@dataclass
class Treatment:
    """Instructs the event service how to persist a violation lifecycle step."""

    kind: Literal["create", "update", "clear"]
    rule: RuleDefinition
    dedup_key: str
    event_id: Optional[str]
    title: str
    severity: Severity
    provenance: Provenance
    timestamp: datetime
    human: str
    machine: dict
    track_ids: list[str]
    observation_id: str
    evidence_quality: Optional[float]


@dataclass
class EngineResult:
    treatments: list[Treatment] = field(default_factory=list)
    evaluations: list[RuleEvaluation] = field(default_factory=list)


class RuleEngine:
    def __init__(
        self,
        *,
        history_length: int = HISTORY_LENGTH,
        stale_track_seconds: float = DEFAULT_STALE_TRACK_SECONDS,
    ) -> None:
        self.history_length = history_length
        self.stale_track_seconds = stale_track_seconds
        self._tracks: dict[str, TrackState] = {}
        self._active: dict[str, ActiveViolation] = {}
        # track_id -> set of region_ids currently containing the track
        self._region_membership: dict[str, set[str]] = {}
        self._region_entered_at: dict[tuple[str, str], datetime] = {}
        # Per-frame region exit transitions recorded in
        # _update_region_membership and consumed by the region_exit evaluator.
        self._region_exits: list[tuple[str, str, datetime]] = []
        # rule_id -> (above_since, active_since)
        self._count_state: dict[str, tuple[Optional[datetime], Optional[datetime]]] = {}
        # dedup_key -> time cooldown expires (for re-trigger suppression)
        self._cooldown_until: dict[str, datetime] = {}

    # -- public API -----------------------------------------------------
    @property
    def active_violations(self) -> dict[str, ActiveViolation]:
        return self._active

    def set_event_id(self, dedup_key: str, event_id: str) -> None:
        if dedup_key in self._active:
            self._active[dedup_key].event_id = event_id

    def active_count(self) -> int:
        return len(self._active)

    def track_snapshot(self) -> list[TrackState]:
        return list(self._tracks.values())

    def process(
        self,
        observation: Observation,
        rules: list[RuleDefinition],
        regions: dict[str, Polygon],
    ) -> EngineResult:
        result = EngineResult()
        now = observation.timestamp
        self._region_exits.clear()
        self._update_tracks(observation)
        self._expire_tracks(now)
        self._update_region_membership(observation, regions)

        seen_keys: set[str] = set()
        for rule in rules:
            if not rule.enabled:
                continue
            try:
                validate_rule(rule, regions)
            except RuleValidationError:
                # Invalid rule is skipped at runtime; creation-time validation
                # prevents this path for operator-defined rules.
                continue
            decisions = self._evaluate_rule(rule, observation, regions)
            for decision in decisions:
                seen_keys.add(decision.dedup_key)
                self._apply_decision(decision, result, observation)

        # Clear violations that are no longer active (condition no longer holds).
        for key, violation in list(self._active.items()):
            if key in seen_keys:
                continue
            rule = _find_rule(rules, violation.rule_id)
            if rule is None:
                # Rule deleted while active: close it out.
                self._emit_clear(violation, None, observation, result, reason="rule_removed")
                continue
            self._emit_clear(violation, rule, observation, result, reason="condition_cleared")

        return result

    # -- track management ----------------------------------------------
    def _update_tracks(self, observation: Observation) -> None:
        for entity in observation.entities:
            if not entity.track_id:
                continue
            point = _entity_point(entity.bbox)
            if point is None:
                continue
            state = self._tracks.get(entity.track_id)
            if state is None:
                state = TrackState(
                    track_id=entity.track_id,
                    class_label=entity.class_label,
                    first_seen=observation.timestamp,
                    last_seen=observation.timestamp,
                )
                self._tracks[entity.track_id] = state
            state.class_label = entity.class_label
            state.last_seen = observation.timestamp
            state.positions.append((observation.timestamp, point))
            while len(state.positions) > self.history_length:
                state.positions.popleft()
            if entity.confidence is not None:
                state.best_confidence = (
                    entity.confidence
                    if state.best_confidence is None
                    else max(state.best_confidence, entity.confidence)
                )

    def _expire_tracks(self, now: datetime) -> None:
        cutoff = now - timedelta(seconds=self.stale_track_seconds)
        for track_id, state in list(self._tracks.items()):
            if state.last_seen < cutoff:
                self._tracks.pop(track_id, None)
                self._region_membership.pop(track_id, None)
                for key in [k for k in self._region_entered_at if k[0] == track_id]:
                    self._region_entered_at.pop(key, None)

    def _update_region_membership(
        self, observation: Observation, regions: dict[str, Polygon]
    ) -> None:
        present_classes = {e.track_id: e.class_label for e in observation.entities if e.track_id}
        for track_id, class_label in present_classes.items():
            state = self._tracks.get(track_id)
            point = state.point() if state else None
            if point is None:
                continue
            memberships = self._region_membership.setdefault(track_id, set())
            for region_id, polygon in regions.items():
                inside = point_in_polygon(point, polygon)
                key = (track_id, region_id)
                was_inside = region_id in memberships
                if inside and not was_inside:
                    memberships.add(region_id)
                    self._region_entered_at[key] = observation.timestamp
                elif not inside and was_inside:
                    memberships.discard(region_id)
                    self._region_entered_at.pop(key, None)
                    self._region_exits.append((track_id, region_id, observation.timestamp))

    # -- rule evaluation ------------------------------------------------
    def _evaluate_rule(
        self,
        rule: RuleDefinition,
        observation: Observation,
        regions: dict[str, Polygon],
    ) -> list["_Decision"]:
        handler = {
            RuleType.region_entry: self._eval_region_entry,
            RuleType.region_exit: self._eval_region_exit,
            RuleType.dwell_time: self._eval_dwell,
            RuleType.wrong_way: self._eval_wrong_way,
            RuleType.count_threshold: self._eval_count,
        }.get(rule.type)
        if handler is None:
            return []
        return handler(rule, observation, regions)

    def _matching_tracks(self, rule: RuleDefinition) -> list[TrackState]:
        class_filter = set(rule.config.class_filter or [])
        tracks = []
        for state in self._tracks.values():
            if class_filter and state.class_label not in class_filter:
                continue
            tracks.append(state)
        return tracks

    def _eval_region_entry(
        self, rule: RuleDefinition, observation: Observation, regions: dict[str, Polygon]
    ) -> list["_Decision"]:
        """Active while a matching track is inside the region.

        The event is created on the first frame the track is inside and stays
        active (updates throttled by dedup) until the track leaves, at which
        point the generic clear step resolves it.
        """
        region_id = rule.config.region_id or ""
        class_filter = set(rule.config.class_filter or [])
        decisions: list["_Decision"] = []
        for state in self._matching_tracks(rule):
            if class_filter and state.class_label not in class_filter:
                continue
            if region_id not in self._region_membership.get(state.track_id, set()):
                continue
            entered_at = self._region_entered_at.get((state.track_id, region_id))
            entered_text = entered_at.isoformat() if entered_at else "unknown"
            decisions.append(
                self._decision(
                    rule,
                    dedup_key=f"{rule.rule_id}:{state.track_id}",
                    title=f"{state.class_label} inside restricted region",
                    track_ids=[state.track_id],
                    observation=observation,
                    condition="entity_inside_region",
                    observed={"region_id": region_id, "class": state.class_label},
                    threshold={"region_id": region_id},
                    human=(
                        f"Track {state.track_id} ({state.class_label}) is inside region "
                        f"'{region_id}' (entered {entered_text})."
                    ),
                    quality=state.best_confidence,
                )
            )
        return decisions

    def _eval_region_exit(
        self, rule: RuleDefinition, observation: Observation, regions: dict[str, Polygon]
    ) -> list["_Decision"]:
        region_id = rule.config.region_id or ""
        class_filter = set(rule.config.class_filter or [])
        decisions: list["_Decision"] = []
        for track_id, exited_region, ts in self._region_exits:
            if exited_region != region_id:
                continue
            state = self._tracks.get(track_id)
            if state is None:
                continue
            if class_filter and state.class_label not in class_filter:
                continue
            decisions.append(
                self._decision(
                    rule,
                    dedup_key=f"{rule.rule_id}:{track_id}",
                    title=f"{state.class_label} left safe region",
                    track_ids=[track_id],
                    observation=observation,
                    condition="entity_exits_region",
                    observed={"region_id": region_id, "class": state.class_label},
                    threshold={"region_id": region_id},
                    human=(
                        f"Track {track_id} ({state.class_label}) exited region "
                        f"'{region_id}' at {ts.isoformat()}."
                    ),
                    quality=state.best_confidence,
                )
            )
        return decisions

    def _eval_dwell(
        self, rule: RuleDefinition, observation: Observation, regions: dict[str, Polygon]
    ) -> list["_Decision"]:
        region_id = rule.config.region_id or ""
        dwell_seconds = rule.config.dwell_seconds or 0.0
        decisions: list["_Decision"] = []
        for state in self._matching_tracks(rule):
            key = (state.track_id, region_id)
            entered_at = self._region_entered_at.get(key)
            if entered_at is None:
                continue
            elapsed = (observation.timestamp - entered_at).total_seconds()
            if elapsed >= dwell_seconds:
                decisions.append(
                    self._decision(
                        rule,
                        dedup_key=f"{rule.rule_id}:{state.track_id}",
                        title=f"{state.class_label} dwelled in region",
                        track_ids=[state.track_id],
                        observation=observation,
                        condition="dwell_exceeds_threshold",
                        observed={
                            "region_id": region_id,
                            "dwell_seconds": round(elapsed, 2),
                            "class": state.class_label,
                        },
                        threshold={"dwell_seconds": dwell_seconds},
                        human=(
                            f"Track {state.track_id} ({state.class_label}) remained in region "
                            f"'{region_id}' for {elapsed:.1f}s (threshold {dwell_seconds:.0f}s)."
                        ),
                        quality=state.best_confidence,
                    )
                )
        return decisions

    def _eval_wrong_way(
        self, rule: RuleDefinition, observation: Observation, regions: dict[str, Polygon]
    ) -> list["_Decision"]:
        allowed = rule.config.allowed_direction_deg or 0.0
        min_disp = rule.config.min_displacement or 0.0
        decisions: list["_Decision"] = []
        for state in self._matching_tracks(rule):
            if len(state.positions) < 2:
                continue
            (t0, p0) = state.positions[0]
            (t1, p1) = state.positions[-1]
            disp = displacement(p0, p1)
            if disp < min_disp:
                continue
            bearing = bearing_degrees(p0, p1)
            if bearing is None:
                continue
            deviation = angular_difference_degrees(bearing, allowed)
            if deviation > (180.0 - WRONG_WAY_TOLERANCE_DEG):
                # Moving roughly opposite to the allowed direction.
                decisions.append(
                    self._decision(
                        rule,
                        dedup_key=f"{rule.rule_id}:{state.track_id}",
                        title=f"{state.class_label} moving against allowed direction",
                        track_ids=[state.track_id],
                        observation=observation,
                        condition="direction_conflicts_with_allowed",
                        observed={
                            "bearing_deg": round(bearing, 1),
                            "image_space_displacement": round(disp, 4),
                            "class": state.class_label,
                        },
                        threshold={
                            "allowed_direction_deg": allowed,
                            "min_displacement": min_disp,
                        },
                        human=(
                            f"Track {state.track_id} ({state.class_label}) moved at "
                            f"{bearing:.0f}° vs allowed {allowed:.0f}° "
                            f"(image-space displacement {disp:.3f})."
                        ),
                        quality=state.best_confidence,
                    )
                )
        return decisions

    def _eval_count(
        self, rule: RuleDefinition, observation: Observation, regions: dict[str, Polygon]
    ) -> list["_Decision"]:
        region_id = rule.config.region_id or ""
        threshold = rule.config.count_threshold or 0
        sustain = rule.config.sustain_seconds or 0.0
        members = [
            state
            for state in self._matching_tracks(rule)
            if region_id in self._region_membership.get(state.track_id, set())
        ]
        count = len(members)
        above_since, _ = self._count_state.get(rule.rule_id, (None, None))
        if count >= threshold:
            if above_since is None:
                above_since = observation.timestamp
                self._count_state[rule.rule_id] = (above_since, None)
            sustained = (observation.timestamp - above_since).total_seconds()
            if sustained >= sustain:
                track_ids = [m.track_id for m in members]
                decisions = [
                    self._decision(
                        rule,
                        dedup_key=f"{rule.rule_id}",
                        title=f"Congestion in region '{region_id}'",
                        track_ids=track_ids,
                        observation=observation,
                        condition="count_at_or_above_threshold",
                        observed={"count": count, "region_id": region_id},
                        threshold={
                            "count_threshold": threshold,
                            "sustain_seconds": sustain,
                        },
                        human=(
                            f"Region '{region_id}' held {count} matching entities "
                            f"(threshold {threshold}) for at least {sustained:.1f}s."
                        ),
                        quality=None,
                    )
                ]
                return decisions
        else:
            self._count_state[rule.rule_id] = (None, None)
        return []

    # -- decision plumbing ---------------------------------------------
    def _decision(
        self,
        rule: RuleDefinition,
        *,
        dedup_key: str,
        title: str,
        track_ids: list[str],
        observation: Observation,
        condition: str,
        observed: dict,
        threshold: dict,
        human: str,
        quality: Optional[float],
    ) -> "_Decision":
        return _Decision(
            rule=rule,
            dedup_key=dedup_key,
            title=title,
            track_ids=track_ids,
            observation_id=observation.observation_id,
            timestamp=observation.timestamp,
            condition=condition,
            observed=observed,
            threshold=threshold,
            human=human,
            quality=quality,
        )

    def _apply_decision(
        self, decision: "_Decision", result: EngineResult, observation: Observation
    ) -> None:
        now = decision.timestamp
        rule = decision.rule
        provenance = Provenance.simulated if observation.is_simulated else Provenance.derived

        # Cooldown gate: skip if a recent clear is still cooling down.
        cooldown_until = self._cooldown_until.get(decision.dedup_key)
        cooldown = rule.config.cooldown_seconds or 0.0

        violation = self._active.get(decision.dedup_key)
        machine = {
            "condition": decision.condition,
            "observed": decision.observed,
            "threshold": decision.threshold,
            "outcome": "triggered",
            "rule_type": rule.type.value,
        }

        if violation is None:
            if cooldown_until is not None and now < cooldown_until:
                return
            violation = ActiveViolation(
                dedup_key=decision.dedup_key,
                rule_id=rule.rule_id,
                rule_version=rule.version,
                first_seen=now,
                last_seen=now,
                track_ids=list(decision.track_ids),
                observation_ids=[decision.observation_id],
            )
            self._active[decision.dedup_key] = violation
            result.treatments.append(
                Treatment(
                    kind="create",
                    rule=rule,
                    dedup_key=decision.dedup_key,
                    event_id=None,
                    title=decision.title,
                    severity=rule.severity,
                    provenance=provenance,
                    timestamp=now,
                    human=decision.human,
                    machine=machine,
                    track_ids=list(decision.track_ids),
                    observation_id=decision.observation_id,
                    evidence_quality=decision.quality,
                )
            )
            result.evaluations.append(
                self._evaluation(rule, decision, observation, EvaluationOutcome.triggered, machine)
            )
        else:
            violation.last_seen = now
            for tid in decision.track_ids:
                if tid not in violation.track_ids:
                    violation.track_ids.append(tid)
            if (
                violation.observation_ids
                and decision.observation_id != violation.observation_ids[-1]
            ):
                violation.observation_ids.append(decision.observation_id)
            dedup = rule.config.dedup_seconds or 0.0
            should_emit = (
                violation.last_update_emitted is None
                or (now - violation.last_update_emitted).total_seconds() >= dedup
            )
            if should_emit:
                violation.last_update_emitted = now
                result.treatments.append(
                    Treatment(
                        kind="update",
                        rule=rule,
                        dedup_key=decision.dedup_key,
                        event_id=violation.event_id,
                        title=decision.title,
                        severity=rule.severity,
                        provenance=provenance,
                        timestamp=now,
                        human=decision.human,
                        machine=machine,
                        track_ids=list(violation.track_ids),
                        observation_id=decision.observation_id,
                        evidence_quality=decision.quality,
                    )
                )

    def _emit_clear(
        self,
        violation: ActiveViolation,
        rule: Optional[RuleDefinition],
        observation: Observation,
        result: EngineResult,
        *,
        reason: str,
    ) -> None:
        self._active.pop(violation.dedup_key, None)
        cooldown = rule.config.cooldown_seconds if rule else 0.0
        if cooldown:
            self._cooldown_until[violation.dedup_key] = observation.timestamp + timedelta(
                seconds=cooldown
            )
        if rule is None or violation.event_id is None:
            return
        result.treatments.append(
            Treatment(
                kind="clear",
                rule=rule,
                dedup_key=violation.dedup_key,
                event_id=violation.event_id,
                title=f"Cleared: {rule.name}",
                severity=rule.severity,
                provenance=Provenance.derived,
                timestamp=observation.timestamp,
                human=f"Condition for rule '{rule.name}' no longer holds ({reason}).",
                machine={
                    "condition": "clear",
                    "reason": reason,
                    "outcome": "cleared",
                    "rule_type": rule.type.value,
                },
                track_ids=list(violation.track_ids),
                observation_id=observation.observation_id,
                evidence_quality=None,
            )
        )

    def _evaluation(
        self,
        rule: RuleDefinition,
        decision: "_Decision",
        observation: Observation,
        outcome: EvaluationOutcome,
        machine: dict,
    ) -> RuleEvaluation:
        return RuleEvaluation(
            schema_version=SCHEMA_VERSION,
            evaluation_id=uuid.uuid4().hex[:16],
            rule_id=rule.rule_id,
            rule_version=rule.version,
            run_id=observation.run_id,
            observation_id=observation.observation_id,
            timestamp=observation.timestamp,
            outcome=outcome,
            condition=decision.condition,
            observed_values=decision.observed,
            threshold=decision.threshold,
            evidence_track_ids=list(decision.track_ids),
            message=decision.human,
            is_simulated=observation.is_simulated,
        )


@dataclass
class _Decision:
    rule: RuleDefinition
    dedup_key: str
    title: str
    track_ids: list[str]
    observation_id: str
    timestamp: datetime
    condition: str
    observed: dict
    threshold: dict
    human: str
    quality: Optional[float]


def _entity_point(bbox: Optional[BoundingBox]) -> Optional[Point]:
    if bbox is None:
        return None
    return bbox.center


def _find_rule(rules: list[RuleDefinition], rule_id: str) -> Optional[RuleDefinition]:
    for rule in rules:
        if rule.rule_id == rule_id:
            return rule
    return None
