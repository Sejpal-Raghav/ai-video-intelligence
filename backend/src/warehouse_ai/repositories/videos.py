"""Video repository for video metadata and cascade lifecycle."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from warehouse_ai.repositories.models import RunModel, VideoModel


def get_video(session: Session, video_id: str) -> VideoModel | None:
    """Query video by ID."""
    stmt = select(VideoModel).where(VideoModel.id == video_id)
    return session.execute(stmt).scalar_one_or_none()


def insert_video(session: Session, video: VideoModel) -> VideoModel:
    """Insert a video record."""
    session.add(video)
    session.flush()
    return video


def list_videos(session: Session, limit: int = 50) -> list[VideoModel]:
    """List recent videos ordered by created_at descending."""
    stmt = select(VideoModel).order_by(VideoModel.created_at.desc()).limit(limit)
    return list(session.execute(stmt).scalars().all())


def is_video_active(session: Session, video_id: str) -> bool:
    """Check if any run for this video is currently QUEUED or RUNNING."""
    stmt = select(RunModel).where(
        RunModel.video_id == video_id,
        RunModel.status.in_(["QUEUED", "RUNNING"]),
    )
    return session.execute(stmt).first() is not None


def delete_video(session: Session, video_id: str) -> bool:
    """Delete a video and trigger cascade deletion of all child records."""
    video = get_video(session, video_id)
    if video is None:
        return False
    session.delete(video)
    session.flush()
    return True
