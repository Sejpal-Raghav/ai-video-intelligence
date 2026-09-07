"""Media asset repository and secure path resolution matching Blueprint Section 15.4."""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from warehouse_ai.repositories.models import MediaAssetModel


class PathTraversalError(ValueError):
    """Raised when a path escapes the configured storage root or contains invalid elements."""
    pass


class MediaNotFoundError(FileNotFoundError):
    """Raised when a media asset or file on disk cannot be found."""
    pass


def resolve_media_path(relative_path: str, storage_root: Path) -> Path:
    """Resolve a database root-relative POSIX path strictly beneath storage_root.

    Rejects:
    - Absolute paths
    - Traversal tokens (e.g. '..')
    - Symlinks along the resolved path
    - Paths that resolve outside storage_root
    """
    if not relative_path:
        raise PathTraversalError("Path cannot be empty")

    p = Path(relative_path)
    if p.is_absolute():
        raise PathTraversalError("Path must be relative, not absolute")

    # Check for traversal components in parts
    if ".." in p.parts:
        raise PathTraversalError("Path contains traversal sequence ('..')")

    root_resolved = storage_root.resolve()
    target_path = (storage_root / p).resolve()

    # Verify target is strictly within storage_root
    try:
        target_path.relative_to(root_resolved)
    except ValueError as err:
        raise PathTraversalError(f"Path resolves outside storage root: {relative_path}") from err

    # Check for symlinks in the path chain between root and target
    curr = target_path
    while curr != root_resolved and curr != curr.parent:
        if curr.is_symlink():
            raise PathTraversalError(f"Symlinks are forbidden in media paths: {curr}")
        curr = curr.parent

    if not target_path.exists() or not target_path.is_file():
        raise MediaNotFoundError(f"Media file does not exist: {relative_path}")

    return target_path


def get_media_asset(session: Session, media_id: str) -> MediaAssetModel | None:
    """Fetch media asset row by ID, or fallback to run_id (NORMALIZED) or video_id (SOURCE)."""
    stmt = select(MediaAssetModel).where(MediaAssetModel.id == media_id)
    asset = session.execute(stmt).scalar_one_or_none()
    if asset:
        return asset
    # Fallback to run normalized video
    stmt_run = select(MediaAssetModel).where(
        MediaAssetModel.run_id == media_id,
        MediaAssetModel.kind == "NORMALIZED",
    )
    asset = session.execute(stmt_run).scalar_one_or_none()
    if asset:
        return asset
    # Fallback to video source
    stmt_vid = select(MediaAssetModel).where(
        MediaAssetModel.video_id == media_id,
        MediaAssetModel.kind == "SOURCE",
    )
    return session.execute(stmt_vid).scalar_one_or_none()


def insert_media_asset(session: Session, asset: MediaAssetModel) -> MediaAssetModel:
    """Insert media asset into session."""
    session.add(asset)
    session.flush()
    return asset
