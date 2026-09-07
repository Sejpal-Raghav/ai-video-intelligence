"""Analytics aggregation service matching Blueprint Section 15.1 & 15.2."""

from __future__ import annotations

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from warehouse_ai.api.errors import ProblemError
from warehouse_ai.api.schemas import AnalyticsScope, AnalyticsSummary, CountItem
from warehouse_ai.repositories.models import EventModel, ReviewModel, RunModel, VideoModel


def get_analytics_summary(
    session: Session,
    run_ids: list[str] | None = None,
    video_ids: list[str] | None = None,
) -> AnalyticsSummary:
    """Compute deterministic analytics summary for up to 20 run_ids OR video_ids."""
    r_ids = run_ids or []
    v_ids = video_ids or []

    if (not r_ids and not v_ids) or (r_ids and v_ids):
        raise ProblemError(
            status_code=400,
            code="MALFORMED_REQUEST",
            title="Invalid analytics scope",
            detail="Specify either repeatable run_ids or repeatable video_ids, but not both.",
        )

    scope_ids = r_ids or v_ids
    if len(scope_ids) > 20:
        raise ProblemError(
            status_code=400,
            code="MALFORMED_REQUEST",
            title="Scope limit exceeded",
            detail=f"At most 20 scope IDs are accepted, received {len(scope_ids)}.",
        )

    # Determine effective run IDs and video IDs
    if v_ids:
        # Find runs for these videos
        stmt = select(RunModel.id).where(RunModel.video_id.in_(v_ids))
        effective_run_ids = list(session.execute(stmt).scalars().all())
        effective_video_ids = v_ids
    else:
        effective_run_ids = r_ids
        stmt = select(distinct(RunModel.video_id)).where(RunModel.id.in_(r_ids))
        effective_video_ids = list(session.execute(stmt).scalars().all())

    # Total source duration ms
    duration_stmt = select(func.coalesce(func.sum(VideoModel.duration_ms), 0)).where(
        VideoModel.id.in_(effective_video_ids)
    )
    total_duration_ms = session.execute(duration_stmt).scalar_one()

    # If no runs found
    if not effective_run_ids:
        return AnalyticsSummary(
            scope=AnalyticsScope(run_ids=r_ids, video_ids=v_ids),
            event_count=0,
            reviewed_count=0,
            by_event_type=[],
            by_risk_tier=[],
            by_review_verdict=[],
            total_source_duration_ms=total_duration_ms,
            false_alert_rate=None,
        )

    # Total event count
    event_count_stmt = select(func.count(EventModel.id)).where(
        EventModel.run_id.in_(effective_run_ids)
    )
    event_count = session.execute(event_count_stmt).scalar_one()

    # Reviewed count (events with >= 1 review)
    reviewed_count_stmt = select(func.count(distinct(ReviewModel.event_id))).join(
        EventModel, EventModel.id == ReviewModel.event_id
    ).where(EventModel.run_id.in_(effective_run_ids))
    reviewed_count = session.execute(reviewed_count_stmt).scalar_one()

    # By event type
    type_stmt = (
        select(EventModel.event_type, func.count(EventModel.id))
        .where(EventModel.run_id.in_(effective_run_ids))
        .group_by(EventModel.event_type)
        .order_by(EventModel.event_type.asc())
    )
    by_type = [CountItem(key=k, count=c) for k, c in session.execute(type_stmt).all()]

    # By risk tier
    tier_stmt = (
        select(EventModel.risk_tier, func.count(EventModel.id))
        .where(EventModel.run_id.in_(effective_run_ids))
        .group_by(EventModel.risk_tier)
        .order_by(EventModel.risk_tier.asc())
    )
    by_tier = [CountItem(key=k, count=c) for k, c in session.execute(tier_stmt).all()]

    # By review verdict (highest revision per event)
    latest_rev_subq = (
        select(
            ReviewModel.event_id,
            func.max(ReviewModel.revision).label("max_rev"),
        )
        .group_by(ReviewModel.event_id)
        .subquery()
    )
    verdict_stmt = (
        select(ReviewModel.verdict, func.count(ReviewModel.event_id))
        .join(
            latest_rev_subq,
            (ReviewModel.event_id == latest_rev_subq.c.event_id)
            & (ReviewModel.revision == latest_rev_subq.c.max_rev),
        )
        .join(EventModel, EventModel.id == ReviewModel.event_id)
        .where(EventModel.run_id.in_(effective_run_ids))
        .group_by(ReviewModel.verdict)
        .order_by(ReviewModel.verdict.asc())
    )
    by_verdict = [CountItem(key=k, count=c) for k, c in session.execute(verdict_stmt).all()]

    return AnalyticsSummary(
        scope=AnalyticsScope(run_ids=r_ids, video_ids=v_ids),
        event_count=event_count,
        reviewed_count=reviewed_count,
        by_event_type=by_type,
        by_risk_tier=by_tier,
        by_review_verdict=by_verdict,
        total_source_duration_ms=total_duration_ms,
        false_alert_rate=None,
    )
