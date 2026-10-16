"""Analytics summary endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query, Request

from ...database import session_scope
from ...schemas import AnalyticsSummary
from ...services import analytics

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary", response_model=AnalyticsSummary)
def analytics_summary(
    request: Request,
    window_hours: int = Query(24, ge=1, le=24 * 90),
    run_id: Optional[str] = None,
) -> AnalyticsSummary:
    """Aggregate event statistics over an explicit time window.

    All values are derived from persisted event records within
    ``[window_start, window_end]``. Simulated data is disclosed via
    ``is_simulated`` and the ``notes`` field.
    """
    with session_scope() as session:
        return analytics.summarize(session, window_hours=window_hours, run_id=run_id)
