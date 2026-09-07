"""Camera profile repository with immutable versioning matching Blueprint Section 12 & 15.2."""

from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from warehouse_ai.repositories.models import CameraProfileModel


def get_camera_profile(
    session: Session, profile_id: str, version: int
) -> CameraProfileModel | None:
    """Get specific version of camera profile."""
    stmt = select(CameraProfileModel).where(
        CameraProfileModel.id == profile_id,
        CameraProfileModel.version == version,
    )
    return session.execute(stmt).scalar_one_or_none()


def get_latest_camera_profile(
    session: Session, profile_id: str
) -> CameraProfileModel | None:
    """Get the latest version of camera profile by ID."""
    stmt = (
        select(CameraProfileModel)
        .where(CameraProfileModel.id == profile_id)
        .order_by(CameraProfileModel.version.desc())
        .limit(1)
    )
    return session.execute(stmt).scalar_one_or_none()


def list_camera_profiles(session: Session) -> list[CameraProfileModel]:
    """List all camera profiles, returning the highest version for each distinct ID."""
    subq = (
        select(
            CameraProfileModel.id,
            func.max(CameraProfileModel.version).label("max_version"),
        )
        .group_by(CameraProfileModel.id)
        .subquery()
    )

    stmt = select(CameraProfileModel).join(
        subq,
        (CameraProfileModel.id == subq.c.id)
        & (CameraProfileModel.version == subq.c.max_version),
    ).order_by(CameraProfileModel.id.asc())

    return list(session.execute(stmt).scalars().all())


def create_camera_profile_version(
    session: Session,
    profile_id: str,
    name: str,
    profile_json: str,
    sha256: str,
    created_at: str | None = None,
) -> CameraProfileModel:
    """Create a new camera profile or append a new version (MAX(version) + 1). Profiles are immutable."""
    max_ver = session.execute(
        select(func.coalesce(func.max(CameraProfileModel.version), 0)).where(
            CameraProfileModel.id == profile_id
        )
    ).scalar_one()

    new_version = max_ver + 1
    now_utc = created_at or datetime.now(timezone.utc).isoformat()

    record = CameraProfileModel(
        id=profile_id,
        version=new_version,
        name=name,
        profile_json=profile_json,
        sha256=sha256,
        created_at=now_utc,
    )
    session.add(record)
    session.flush()
    return record
