"""Camera profile configuration and immutable versioning routes."""

from __future__ import annotations

import hashlib
import json
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from warehouse_ai.api.dependencies import get_db_session
from warehouse_ai.api.schemas import CameraProfileCreate, CameraProfileResponse
from warehouse_ai.repositories.camera_profiles import (
    create_camera_profile_version,
    list_camera_profiles,
)

router = APIRouter(prefix="/api/v1/camera-profiles", tags=["camera-profiles"])


def compute_canonical_profile_sha256(data: dict) -> str:
    """Compute SHA-256 over canonical JSON excluding profile_sha256/sha256 per Section 12.1."""
    clean = {k: v for k, v in data.items() if k not in ("sha256", "profile_sha256")}
    canonical = json.dumps(clean, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@router.get("", response_model=list[CameraProfileResponse])
def get_camera_profiles(
    session: Session = Depends(get_db_session),
) -> list[CameraProfileResponse]:
    """List all camera profiles returning the latest version for each distinct ID."""
    records = list_camera_profiles(session)
    result = []
    for r in records:
        data = json.loads(r.profile_json)
        result.append(
            CameraProfileResponse(
                schema_version="camera-profile.v1",
                id=r.id,
                version=r.version,
                name=r.name,
                camera_motion="FIXED",
                frame_aspect_ratio=data.get("frame_aspect_ratio", 1.777778),
                floor_polygon=data.get("floor_polygon", []),
                zones=data.get("zones", []),
                support_regions=data.get("support_regions", []),
                created_at=r.created_at,
                sha256=r.sha256,
            )
        )
    return result


@router.post("", status_code=status.HTTP_201_CREATED, response_model=CameraProfileResponse)
def post_camera_profile(
    payload: CameraProfileCreate,
    session: Session = Depends(get_db_session),
) -> CameraProfileResponse:
    """Create an immutable camera profile version (MAX(version) + 1)."""
    raw_dict = payload.model_dump()
    sha256 = compute_canonical_profile_sha256(raw_dict)
    profile_json = json.dumps(raw_dict, sort_keys=True)

    record = create_camera_profile_version(
        session=session,
        profile_id=payload.id,
        name=payload.name,
        profile_json=profile_json,
        sha256=sha256,
    )
    session.commit()

    return CameraProfileResponse(
        schema_version="camera-profile.v1",
        id=record.id,
        version=record.version,
        name=record.name,
        camera_motion="FIXED",
        frame_aspect_ratio=payload.frame_aspect_ratio,
        floor_polygon=payload.floor_polygon,
        zones=payload.zones,
        support_regions=payload.support_regions,
        created_at=record.created_at,
        sha256=record.sha256,
    )
