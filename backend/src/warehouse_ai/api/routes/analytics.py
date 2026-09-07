"""Analytics summary endpoint matching Blueprint Section 15.1 & 15.2."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from warehouse_ai.api.dependencies import get_db_session
from warehouse_ai.api.schemas import AnalyticsSummary
from warehouse_ai.services.analytics import get_analytics_summary

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/summary", response_model=AnalyticsSummary)
def get_summary(
    run_id: list[str] | None = Query(default=None),
    video_id: list[str] | None = Query(default=None),
    session: Session = Depends(get_db_session),
) -> AnalyticsSummary:
    """Deterministic analytics summary for up to 20 run_ids or video_ids."""
    return get_analytics_summary(session, run_ids=run_id, video_ids=video_id)
