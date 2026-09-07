"""Retention and quarantine deletion service matching Blueprint Section 8.4."""

from __future__ import annotations

import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.orm import Session

from warehouse_ai.repositories.models import RunModel, VideoModel
from warehouse_ai.repositories.videos import delete_video, is_video_active


class VideoActiveConflictError(Exception):
    """Raised when trying to delete a video while a child run is active."""
    pass


def purge_staging(storage_root: Path, max_age_hours: float = 1.0) -> int:
    """Purge incomplete staging files older than max_age_hours."""
    staging_dir = storage_root / ".staging"
    if not staging_dir.exists():
        return 0

    now = time.time()
    cutoff = now - (max_age_hours * 3600)
    purged = 0

    for item in staging_dir.glob("*.part"):
        try:
            if item.stat().st_mtime < cutoff:
                item.unlink()
                purged += 1
        except OSError:
            pass

    return purged


def delete_video_with_quarantine(
    session: Session, video_id: str, storage_root: Path
) -> bool:
    """Manually delete a video using quarantine directory pattern.

    1. Checks if video has active (QUEUED/RUNNING) child runs -> raises VideoActiveConflictError (409)
    2. Moves video directory and child run directories under storage/.deleting/<operation_uuid>/
    3. Deletes database rows in one transaction
    4. Permanently removes quarantined directory
    """
    if is_video_active(session, video_id):
        raise VideoActiveConflictError(
            f"Cannot delete video {video_id}: one or more child runs are active (QUEUED or RUNNING)"
        )

    # Collect run IDs for this video
    runs = session.execute(select(RunModel.id).where(RunModel.video_id == video_id)).scalars().all()

    op_uuid = str(uuid.uuid4())
    quarantine_dir = storage_root / ".deleting" / op_uuid
    quarantine_dir.mkdir(parents=True, exist_ok=True)

    # Quarantine video directory
    video_dir = storage_root / "videos" / video_id
    if video_dir.exists() and video_dir.is_dir():
        target = quarantine_dir / "videos" / video_id
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(video_dir), str(target))

    # Quarantine run directories
    for run_id in runs:
        run_dir = storage_root / "runs" / run_id
        if run_dir.exists() and run_dir.is_dir():
            target = quarantine_dir / "runs" / run_id
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(run_dir), str(target))

    # Delete from DB
    deleted = delete_video(session, video_id)
    session.commit()

    # Permanently delete quarantine directory
    try:
        shutil.rmtree(str(quarantine_dir))
    except OSError:
        pass

    return deleted


def run_retention_pass(session: Session, storage_root: Path) -> int:
    """Automatic retention pass scanning for expired videos.

    Skips videos with queued/running child runs.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    stmt = select(VideoModel).where(VideoModel.expires_at <= now_iso)
    expired_videos = list(session.execute(stmt).scalars().all())

    deleted_count = 0
    for video in expired_videos:
        if is_video_active(session, video.id):
            # Skip video with active runs; reevaluated on next pass
            continue
        try:
            delete_video_with_quarantine(session, video.id, storage_root)
            deleted_count += 1
        except Exception:
            session.rollback()

    purge_staging(storage_root, max_age_hours=1.0)
    return deleted_count
