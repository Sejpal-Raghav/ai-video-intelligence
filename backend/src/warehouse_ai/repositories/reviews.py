"""Review repository with append-only revisions matching Blueprint Section 14.2 & 15.2."""

from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from warehouse_ai.repositories.models import ReviewModel


class ReviewConflictError(Exception):
    """Raised when concurrent revision insertion conflicts after retry."""
    pass


def get_latest_review(session: Session, event_id: str) -> ReviewModel | None:
    """Fetch the latest revision review for an event."""
    stmt = (
        select(ReviewModel)
        .where(ReviewModel.event_id == event_id)
        .order_by(ReviewModel.revision.desc())
        .limit(1)
    )
    return session.execute(stmt).scalar_one_or_none()


def list_reviews_for_event(session: Session, event_id: str) -> list[ReviewModel]:
    """List all review revisions for an event in ascending revision order."""
    stmt = (
        select(ReviewModel)
        .where(ReviewModel.event_id == event_id)
        .order_by(ReviewModel.revision.asc())
    )
    return list(session.execute(stmt).scalars().all())


def append_review(
    session: Session,
    review_id: str,
    event_id: str,
    verdict: str,
    reviewer_name: str,
    note: str = "",
    max_retries: int = 2,
) -> ReviewModel:
    """Append a new review revision using atomic MAX(revision) + 1.

    Retries once on concurrent revision conflict before raising ReviewConflictError.
    """
    now_utc = datetime.now(timezone.utc).isoformat()

    for attempt in range(max_retries):
        try:
            # Query current max revision
            max_rev = session.execute(
                select(func.coalesce(func.max(ReviewModel.revision), 0)).where(
                    ReviewModel.event_id == event_id
                )
            ).scalar_one()

            new_revision = max_rev + 1
            review = ReviewModel(
                id=review_id,
                event_id=event_id,
                revision=new_revision,
                verdict=verdict,
                note=note,
                reviewer_name=reviewer_name,
                created_at=now_utc,
            )
            session.add(review)
            session.flush()
            return review
        except IntegrityError as err:
            session.rollback()
            if attempt == max_retries - 1:
                raise ReviewConflictError(
                    f"Concurrent revision conflict appending review for event {event_id}"
                ) from err

    raise ReviewConflictError("Failed to append review revision")
