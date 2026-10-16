"""Deterministic scripted demo scenarios.

A scenario is a set of waypoint-interpolated tracks plus named regions. The
same scenario is used by the mock adapter (to produce clearly-labelled
SIMULATED observations) and by tests (to assert deterministic rule outcomes).
No PipeGen or real inference is involved here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..schemas import Point, Polygon


@dataclass(frozen=True)
class Waypoint:
    t: float  # seconds from scenario start
    x: float  # normalized 0..1
    y: float  # normalized 0..1


@dataclass(frozen=True)
class ScriptedTrack:
    track_id: str
    class_label: str
    waypoints: list[Waypoint]
    confidence: float = 0.8

    @property
    def start_time(self) -> float:
        return self.waypoints[0].t

    @property
    def end_time(self) -> float:
        return self.waypoints[-1].t

    def position_at(self, t: float) -> Point | None:
        """Piecewise-linear interpolation. Returns None when inactive."""
        if t < self.start_time or t > self.end_time:
            return None
        points = self.waypoints
        for i in range(len(points) - 1):
            a, b = points[i], points[i + 1]
            if a.t <= t <= b.t:
                if b.t == a.t:
                    return Point(x=a.x, y=a.y)
                frac = (t - a.t) / (b.t - a.t)
                return Point(x=a.x + (b.x - a.x) * frac, y=a.y + (b.y - a.y) * frac)
        last = points[-1]
        return Point(x=last.x, y=last.y)


@dataclass(frozen=True)
class ScenarioRegion:
    region_id: str
    name: str
    polygon: Polygon


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    duration: float
    tracks: list[ScriptedTrack]
    regions: list[ScenarioRegion] = field(default_factory=list)
    loop: bool = True


def workshop_scenario() -> Scenario:
    """A fixed-view workshop scene with normal and anomalous phases.

    Phases (seconds):
      0-12   normal: two people moving along a normal path (east).
      2-13   anomaly: a person enters the restricted zone and dwells.
      4-14   anomaly: a person moves west against the allowed east direction.
    The scenario loops every ``duration`` seconds so the demo is repeatable.
    """
    restricted = Polygon(
        points=[
            Point(x=0.05, y=0.10),
            Point(x=0.35, y=0.10),
            Point(x=0.35, y=0.55),
            Point(x=0.05, y=0.55),
        ]
    )
    work_area = Polygon(
        points=[
            Point(x=0.45, y=0.55),
            Point(x=0.92, y=0.55),
            Point(x=0.92, y=0.95),
            Point(x=0.45, y=0.95),
        ]
    )

    tracks = [
        # Normal eastbound walker across the lower aisle (should NOT trigger
        # wrong-way or region rules).
        ScriptedTrack(
            track_id="sim-north-1",
            class_label="person",
            waypoints=[
                Waypoint(t=0.0, x=0.12, y=0.72),
                Waypoint(t=10.0, x=0.86, y=0.72),
            ],
            confidence=0.86,
        ),
        # Normal loop near the work area (no wrong-way: returns slowly east/north).
        ScriptedTrack(
            track_id="sim-loop-2",
            class_label="person",
            waypoints=[
                Waypoint(t=1.0, x=0.55, y=0.62),
                Waypoint(t=7.0, x=0.85, y=0.62),
                Waypoint(t=13.0, x=0.80, y=0.85),
                Waypoint(t=19.0, x=0.55, y=0.62),
            ],
            confidence=0.79,
        ),
        # Anomalous: enters the restricted zone (~t=2) and dwells until ~t=13.
        ScriptedTrack(
            track_id="sim-intruder-3",
            class_label="person",
            waypoints=[
                Waypoint(t=0.5, x=0.30, y=0.85),
                Waypoint(t=2.5, x=0.22, y=0.35),  # crosses into restricted zone
                Waypoint(t=8.0, x=0.28, y=0.30),
                Waypoint(t=13.0, x=0.20, y=0.28),  # dwelt > dwell threshold
                Waypoint(t=15.5, x=0.20, y=0.85),  # leaves zone
            ],
            confidence=0.83,
        ),
        # Anomalous: moves WEST against the allowed EAST direction.
        ScriptedTrack(
            track_id="sim-wrongway-4",
            class_label="person",
            waypoints=[
                Waypoint(t=4.0, x=0.88, y=0.72),
                Waypoint(t=12.0, x=0.14, y=0.72),
            ],
            confidence=0.77,
        ),
    ]

    return Scenario(
        name="workshop",
        description=(
            "Fixed-view workshop. Normal eastbound movement plus two anomalous "
            "tracks: a restricted-zone intrusion with dwell, and wrong-way motion."
        ),
        duration=22.0,
        tracks=tracks,
        regions=[
            ScenarioRegion("region_restricted", "Restricted Zone", restricted),
            ScenarioRegion("region_work", "Work Area", work_area),
        ],
        loop=True,
    )
