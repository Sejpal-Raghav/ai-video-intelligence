"""Event repository with cursor pagination and filtering matching Blueprint Section 15.1 & 15.2."""

from __future__ import annotations

import base64
import json
from typing import Any
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from warehouse_ai.repositories.models import EventModel, ReviewModel


class InvalidCursorError(ValueError):
    """Raised when cursor decoding or structure validation fails."""
    pass


def encode_cursor(created_at: str, event_id: str) -> str:
    """Encode created_at and id into an unpadded URL-safe base64 cursor."""
    payload = json.dumps({"created_at": created_at, "id": event_id}, separators=(",", ":"))
    encoded = base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")
    return encoded.rstrip("=")


def decode_cursor(cursor: str) -> tuple[str, str]:
    """Decode unpadded URL-safe base64 cursor and return (created_at, id)."""
    try:
        # Re-add padding if needed
        padding = 4 - (len(cursor) % 4)
        padded = cursor + ("=" * (padding % 4))
        raw = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise InvalidCursorError("Cursor must be a JSON object")
        created_at = data.get("created_at")
        item_id = data.get("id")
        if not created_at or not item_id or not isinstance(created_at, str) or not isinstance(item_id, str):
            raise InvalidCursorError("Cursor missing created_at or id")
        return created_at, item_id
    except Exception as err:
        raise InvalidCursorError(f"Invalid cursor format: {err}") from err


def get_event(session: Session, event_id: str) -> EventModel | None:
    """Get event by ID."""
    stmt = select(EventModel).where(EventModel.id == event_id)
    return session.execute(stmt).scalar_one_or_none()


def insert_events(session: Session, events: list[EventModel]) -> list[EventModel]:
    """Bulk insert events."""
    session.add_all(events)
    session.flush()
    return events


def list_events(
    session: Session,
    run_id: str | None = None,
    event_types: list[str] | None = None,
    risk_tiers: list[str] | None = None,
    review_verdict: str | None = None,
    start_ms: int | None = None,
    end_ms: int | None = None,
    cursor: str | None = None,
    limit: int = 50,
) -> tuple[list[EventModel], str | None]:
    """List events matching filters with cursor pagination.

    Limits capped at 100, default 50.
    Returns (items, next_cursor).
    """
    limit = max(1, min(limit, 100))
    stmt = select(EventModel)

    if run_id:
        stmt = stmt.where(EventModel.run_id == run_id)

    if event_types:
        stmt = stmt.where(EventModel.event_type.in_(event_types))

    if risk_tiers:
        stmt = stmt.where(EventModel.risk_tier.in_(risk_tiers))

    # Time overlap requires run_id per Section 15.1
    if start_ms is not None or end_ms is not None:
        if not run_id:
            raise ValueError("start_ms and end_ms filtering requires run_id")
        if start_ms is not None and end_ms is not None:
            # Overlap: event.end_ms >= start_ms AND event.start_ms <= end_ms
            stmt = stmt.where(EventModel.end_ms >= start_ms, EventModel.start_ms <= end_ms)
        elif start_ms is not None:
            stmt = stmt.where(EventModel.end_ms >= start_ms)
        elif end_ms is not None:
            stmt = stmt.where(EventModel.start_ms <= end_ms)

    # Filter by review verdict on highest revision if requested
    if review_verdict:
        latest_rev_subq = (
            select(
                ReviewModel.event_id,
                func.max(ReviewModel.revision).label("max_rev"),
            )
            .group_by(ReviewModel.event_id)
            .subquery()
        )
        verdict_subq = (
            select(ReviewModel.event_id)
            .join(
                latest_rev_subq,
                (ReviewModel.event_id == latest_rev_subq.c.event_id)
                & (ReviewModel.revision == latest_rev_subq.c.max_rev),
            )
            .where(ReviewModel.verdict == review_verdict)
            .subquery()
        )
        stmt = stmt.where(EventModel.id.in_(select(verdict_subq.c.event_id)))

    # Cursor ordering: created_at DESC, id DESC
    if cursor:
        cursor_created_at, cursor_id = decode_cursor(cursor)
        stmt = stmt.where(
            or_(
                EventModel.created_at < cursor_created_at,
                (EventModel.created_at == cursor_created_at) & (EventModel.id < cursor_id),
            )
        )

    stmt = stmt.order_by(EventModel.created_at.desc(), EventModel.id.desc()).limit(limit + 1)
    results = list(session.execute(stmt).scalars().all())

    next_cursor: str | None = None
    if len(results) > limit:
        items = results[:limit]
        last_item = items[-1]
        next_cursor = encode_cursor(last_item.created_at, last_item.id)
    else:
        items = results

    return items, next_cursor
