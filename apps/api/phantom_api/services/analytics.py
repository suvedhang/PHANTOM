"""Analytics aggregation over persisted events."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from .. import repository as repo
from ..schemas import AnalyticsSummary


def summarize(
    session: Session,
    *,
    window_hours: int = 24,
    run_id: Optional[str] = None,
) -> AnalyticsSummary:
    window_end = datetime.now(tz=timezone.utc)
    window_start = window_end - timedelta(hours=window_hours)

    rows = [r for r in repo.events_in_window(session, window_start, window_end)]
    if run_id:
        rows = [r for r in rows if r.run_id == run_id]

    by_severity: Counter[str] = Counter()
    by_rule: Counter[str] = Counter()
    by_status: Counter[str] = Counter()
    durations: list[float] = []
    is_simulated = False

    for row in rows:
        by_severity[row.severity] += 1
        by_rule[row.rule_id] += 1
        by_status[row.status] += 1
        if row.is_simulated:
            is_simulated = True
        duration = (row.last_seen - row.created_at).total_seconds()
        if duration >= 0:
            durations.append(duration)

    # Events over time bucketed by hour (bounded to the window).
    buckets: dict[str, int] = {}
    for row in rows:
        key = row.created_at.replace(minute=0, second=0, microsecond=0).isoformat()
        buckets[key] = buckets.get(key, 0) + 1
    over_time = [
        {"bucket_start": key, "count": count} for key, count in sorted(buckets.items())
    ]

    notes: list[str] = []
    if not rows:
        notes.append("No events in the selected window.")
    if is_simulated:
        notes.append(
            "Window includes SIMULATED events (demo mode). Not real pipeline evidence."
        )

    return AnalyticsSummary(
        window_start=window_start,
        window_end=window_end,
        total_events=len(rows),
        active_events=sum(1 for r in rows if r.status in ("active", "acknowledged")),
        events_by_severity=dict(by_severity),
        events_by_rule=dict(by_rule),
        events_by_status=dict(by_status),
        events_over_time=over_time,
        average_active_duration_seconds=(
            round(sum(durations) / len(durations), 2) if durations else None
        ),
        is_simulated=is_simulated,
        sample_count=len(rows),
        notes=notes,
    )
