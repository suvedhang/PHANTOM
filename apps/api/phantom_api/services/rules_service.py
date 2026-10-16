"""Conversion and validation between persistence rows and domain models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from .. import db_models as m
from ..rule_engine.engine import SUPPORTED_RULE_TYPES, RuleValidationError, validate_rule
from ..schemas import (
    Polygon,
    Point,
    RegionModel,
    RuleConfig,
    RuleDefinition,
    RuleType,
    Severity,
)


def region_row_to_model(row: m.RegionRow) -> RegionModel:
    return RegionModel(
        region_id=row.region_id,
        name=row.name,
        polygon=Polygon(points=[Point(**p) for p in row.polygon]),
        enabled=row.enabled,
        version=row.version,
    )


def rule_row_to_definition(row: m.RuleRow) -> RuleDefinition:
    created = _as_utc(row.created_at)
    updated = _as_utc(row.updated_at)
    return RuleDefinition(
        rule_id=row.rule_id,
        name=row.name,
        description=row.description,
        type=RuleType(row.type),
        config=RuleConfig(**row.config),
        severity=Severity(row.severity),
        enabled=row.enabled,
        version=row.version,
        created_at=created,
        updated_at=updated,
    )


def regions_by_id(region_rows: list[m.RegionRow]) -> dict[str, Polygon]:
    return {
        row.region_id: Polygon(points=[Point(**p) for p in row.polygon])
        for row in region_rows
        if row.enabled
    }


def validate_rule_definition(
    rule: RuleDefinition, regions: dict[str, Polygon]
) -> None:
    """Validate a rule; raises :class:`RuleValidationError` on problems."""
    validate_rule(rule, regions)


def ensure_supported_type(rule_type: RuleType) -> None:
    if rule_type not in SUPPORTED_RULE_TYPES:
        supported = ", ".join(sorted(t.value for t in SUPPORTED_RULE_TYPES))
        raise RuleValidationError(
            f"Rule type '{rule_type.value}' is not supported. Supported: {supported}."
        )


def _as_utc(value: Optional[datetime]) -> datetime:
    if value is None:
        return datetime.now(tz=timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
