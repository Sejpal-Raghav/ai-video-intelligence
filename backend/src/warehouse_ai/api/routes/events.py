"""Event query, detail, and human review endpoints."""

from __future__ import annotations

import gzip
import json
import uuid
from typing import Any, Literal
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from warehouse_ai.api.dependencies import get_app_settings, get_db_session
from warehouse_ai.api.errors import ProblemError
from warehouse_ai.api.schemas import (
    EventDetail,
    EventPage,
    MediaLinks,
    ReviewCreate,
    ReviewResponse,
    RiskDetail,
)
from warehouse_ai.config import Settings
from warehouse_ai.repositories.events import InvalidCursorError, get_event, list_events
from warehouse_ai.repositories.media import (
    MediaNotFoundError,
    PathTraversalError,
    resolve_media_path,
)
from warehouse_ai.repositories.models import EventModel, MediaAssetModel
from warehouse_ai.repositories.reviews import (
    ReviewConflictError,
    append_review,
    get_latest_review,
)

router = APIRouter(prefix="/api/v1/events", tags=["events"])

# Padding applied around [start_ms, end_ms] when returning track frames for the
# bounding-box overlay, matching the clip padding used in evidence/clips.py so
# the overlay's time range always covers the full playable clip.
_TRACKS_WINDOW_PADDING_MS = 1500


def build_event_detail(session: Session, event: EventModel) -> EventDetail:
    """Construct EventDetail DTO with parsed facts, explanation, media links, and latest review."""
    try:
        facts = json.loads(event.facts_json)
    except Exception:
        facts = {}

    # Find media IDs for clip and thumbnail
    clip_stmt = select(MediaAssetModel.id).where(
        MediaAssetModel.event_id == event.id,
        MediaAssetModel.kind == "EVENT_CLIP",
    )
    clip_id = session.execute(clip_stmt).scalar_one_or_none()

    thumb_stmt = select(MediaAssetModel.id).where(
        MediaAssetModel.event_id == event.id,
        MediaAssetModel.kind == "THUMBNAIL",
    )
    thumb_id = session.execute(thumb_stmt).scalar_one_or_none()

    latest_rev = get_latest_review(session, event.id)
    review_dto = None
    if latest_rev:
        review_dto = ReviewResponse(
            id=latest_rev.id,
            event_id=latest_rev.event_id,
            revision=latest_rev.revision,
            verdict=latest_rev.verdict,  # type: ignore
            note=latest_rev.note,
            reviewer_name=latest_rev.reviewer_name,
            created_at=latest_rev.created_at,
        )

    # Explanation: use the rich natural-language text computed by RiskEngine and stored in
    # decision_trace_json, falling back to facts_json["explanation"], then to the generic stub.
    try:
        trace: dict[str, Any] = json.loads(event.decision_trace_json)
        explanation: str = (
            trace.get("explanation")
            or facts.get("explanation")
            or f"Detected {event.event_type.replace('_', ' ').lower()} event "
               f"from {event.start_ms / 1000.0:.1f}s to {event.end_ms / 1000.0:.1f}s "
               f"(Track ID {event.primary_track_id})."
        )
    except Exception:
        trace = {}
        explanation = (
            f"Detected {event.event_type.replace('_', ' ').lower()} event "
            f"from {event.start_ms / 1000.0:.1f}s to {event.end_ms / 1000.0:.1f}s "
            f"(Track ID {event.primary_track_id})."
        )

    return EventDetail(
        id=event.id,
        run_id=event.run_id,
        event_type=event.event_type,  # type: ignore
        start_ms=event.start_ms,
        end_ms=event.end_ms,
        primary_track_id=event.primary_track_id,
        risk=RiskDetail(
            score=event.risk_score,
            tier=event.risk_tier,  # type: ignore
            policy_version="v1",
        ),
        evidence_quality=event.evidence_quality,
        verification_status=event.verification_status,  # type: ignore
        facts=facts,
        explanation=explanation,
        decision_trace=trace or None,
        media=MediaLinks(clip_id=clip_id, thumbnail_id=thumb_id),
        review=review_dto,
    )


@router.get("", response_model=EventPage)
def get_events(
    run_id: str | None = Query(default=None),
    event_type: list[str] | None = Query(default=None),
    risk_tier: list[str] | None = Query(default=None),
    review_verdict: str | None = Query(default=None),
    start_ms: int | None = Query(default=None, ge=0),
    end_ms: int | None = Query(default=None, ge=0),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    session: Session = Depends(get_db_session),
) -> EventPage:
    """List events matching filters with cursor pagination."""
    try:
        items, next_cursor = list_events(
            session=session,
            run_id=run_id,
            event_types=event_type,
            risk_tiers=risk_tier,
            review_verdict=review_verdict,
            start_ms=start_ms,
            end_ms=end_ms,
            cursor=cursor,
            limit=limit,
        )
    except InvalidCursorError as err:
        raise ProblemError(
            status_code=400,
            code="INVALID_CURSOR",
            title="Invalid pagination cursor",
            detail=str(err),
        ) from err
    except ValueError as err:
        raise ProblemError(
            status_code=400,
            code="MALFORMED_REQUEST",
            title="Invalid query parameter",
            detail=str(err),
        ) from err

    detail_items = [build_event_detail(session, evt) for evt in items]
    return EventPage(items=detail_items, next_cursor=next_cursor)


@router.get("/{event_id}", response_model=EventDetail)
def get_event_by_id(
    event_id: str,
    session: Session = Depends(get_db_session),
) -> EventDetail:
    """Retrieve event details, facts, trace, and media links by ID."""
    event = get_event(session, event_id)
    if not event:
        raise ProblemError(
            status_code=404,
            code="EVENT_NOT_FOUND",
            title="Event not found",
            detail=f"Event with ID {event_id} was not found.",
        )

    return build_event_detail(session, event)


@router.get("/{event_id}/tracks", response_model=list[dict[str, Any]])
def get_event_tracks(
    event_id: str,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> list[dict[str, Any]]:
    """Return decoded track frames (bounding boxes) for the window around one event.

    Reads the run's TRACKS media asset (tracks.jsonl.gz), filters to the event's
    [start_ms, end_ms] window padded by _TRACKS_WINDOW_PADDING_MS on each side
    (matching the evidence clip's own padding), and returns plain JSON so the
    frontend bounding-box overlay can render without any gzip/JSONL parsing
    library on the client.
    """
    event = get_event(session, event_id)
    if not event:
        raise ProblemError(
            status_code=404,
            code="EVENT_NOT_FOUND",
            title="Event not found",
            detail=f"Event with ID {event_id} was not found.",
        )

    tracks_stmt = select(MediaAssetModel).where(
        MediaAssetModel.run_id == event.run_id,
        MediaAssetModel.kind == "TRACKS",
    )
    tracks_asset = session.execute(tracks_stmt).scalar_one_or_none()
    if not tracks_asset:
        raise ProblemError(
            status_code=404,
            code="TRACKS_NOT_FOUND",
            title="Track data not found",
            detail=f"No TRACKS asset was found for run {event.run_id}.",
        )

    try:
        file_path = resolve_media_path(tracks_asset.relative_path, settings.storage_root_path)
    except (PathTraversalError, MediaNotFoundError) as err:
        raise ProblemError(
            status_code=404,
            code="TRACKS_NOT_FOUND",
            title="Track file not found",
            detail=str(err),
        ) from err

    window_start = max(0, event.start_ms - _TRACKS_WINDOW_PADDING_MS)
    window_end = event.end_ms + _TRACKS_WINDOW_PADDING_MS

    frames: list[dict[str, Any]] = []
    with gzip.open(file_path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = obj.get("timestamp_ms", 0)
            if window_start <= ts <= window_end:
                frames.append(obj)

    return frames


@router.post(
    "/{event_id}/reviews",
    status_code=status.HTTP_201_CREATED,
    response_model=ReviewResponse,
)
def post_event_review(
    event_id: str,
    payload: ReviewCreate,
    session: Session = Depends(get_db_session),
) -> ReviewResponse:
    """Append a human review revision for an event."""
    event = get_event(session, event_id)
    if not event:
        raise ProblemError(
            status_code=404,
            code="EVENT_NOT_FOUND",
            title="Event not found",
            detail=f"Event with ID {event_id} was not found.",
        )

    review_id = str(uuid.uuid4())
    try:
        rev = append_review(
            session=session,
            review_id=review_id,
            event_id=event_id,
            verdict=payload.verdict,
            reviewer_name=payload.reviewer_name,
            note=payload.note,
        )
        session.commit()
        return ReviewResponse(
            id=rev.id,
            event_id=rev.event_id,
            revision=rev.revision,
            verdict=rev.verdict,  # type: ignore
            note=rev.note,
            reviewer_name=rev.reviewer_name,
            created_at=rev.created_at,
        )
    except ReviewConflictError as err:
        raise ProblemError(
            status_code=409,
            code="REVIEW_CONFLICT",
            title="Review revision conflict",
            detail="A concurrent review was recorded. Please refresh and retry.",
        ) from err
