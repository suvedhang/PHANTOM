"""Development/demo seed data.

Everything seeded here is labelled and safe to reset. Seed rules use the
``rule_seed_`` prefix so the demo reset routine can find and remove them
without touching operator-created rules. Seed data is NEVER presented as real
inference output.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from .. import db_models as m
from .. import repository as repo
from ..demo.scenarios import workshop_scenario
from ..logging_config import get_logger
from ..schemas import RuleType, Severity

logger = get_logger("phantom.seed")

_SEED_RULES: list[tuple[str, str, str, str, dict, str]] = [
    (
        "rule_seed_restricted_entry",
        "Restricted Zone Entry",
        "Trigger when any tracked entity enters the configured restricted zone.",
        RuleType.region_entry.value,
        {
            "region_id": "region_restricted",
            "class_filter": [],
            "cooldown_seconds": 20.0,
            "dedup_seconds": 2.0,
        },
        Severity.high.value,
    ),
    (
        "rule_seed_dwell",
        "Excessive Dwell In Restricted Zone",
        "Trigger when an entity remains inside the restricted zone longer than "
        "the configured duration.",
        RuleType.dwell_time.value,
        {
            "region_id": "region_restricted",
            "class_filter": [],
            "dwell_seconds": 5.0,
            "cooldown_seconds": 20.0,
            "dedup_seconds": 2.0,
        },
        Severity.medium.value,
    ),
    (
        "rule_seed_wrongway",
        "Wrong-Way Movement",
        "Trigger when a track's image-space displacement runs against the "
        "configured allowed direction (east) beyond the minimum displacement.",
        RuleType.wrong_way.value,
        {
            "region_id": None,
            "class_filter": ["person"],
            "allowed_direction_deg": 0.0,
            "min_displacement": 0.15,
            "cooldown_seconds": 20.0,
            "dedup_seconds": 2.0,
        },
        Severity.high.value,
    ),
]


def seed_regions(session: Session) -> None:
    scenario = workshop_scenario()
    for region in scenario.regions:
        if repo.get_region(session, region.region_id) is None:
            repo.upsert_region(
                session,
                region_id=region.region_id,
                name=region.name,
                polygon=[p.model_dump() for p in region.polygon.points],
                enabled=True,
            )


def seed_rules(session: Session) -> None:
    for rule_id, name, description, rtype, config, severity in _SEED_RULES:
        if repo.get_rule(session, rule_id) is not None:
            continue
        row = m.RuleRow(
            rule_id=rule_id,
            name=name,
            description=description,
            type=rtype,
            config=config,
            severity=severity,
            enabled=True,
            version=1,
        )
        session.add(row)
        session.flush()
        session.add(
            m.RuleVersionRow(
                rule_id=rule_id,
                version=1,
                snapshot={
                    "rule_id": rule_id,
                    "name": name,
                    "description": description,
                    "type": rtype,
                    "config": config,
                    "severity": severity,
                    "enabled": True,
                    "version": 1,
                },
            )
        )
    session.flush()


def seed_all(session: Session) -> None:
    seed_regions(session)
    seed_rules(session)
    logger.info("demo seed complete", extra={"component": "seed"})
