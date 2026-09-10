"""Run management and query endpoints."""

from __future__ import annotations

import json
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from warehouse_ai.api.dependencies import get_app_settings, get_db_session
from warehouse_ai.api.errors import ProblemError
from warehouse_ai.api.schemas import RunAccepted, RunCreate, RunDetail
from warehouse_ai.config import Settings
from warehouse_ai.repositories.models import MediaAssetModel
from warehouse_ai.repositories.runs import get_run, list_runs
from warehouse_ai.services.run_service import enqueue_run

router = APIRouter(prefix="/api/v1/runs", tags=["runs"])


def _get_manifest_media_id(session: Session, run_id: str) -> str | None:
    """Return the media asset id for the MANIFEST file of a run, or None if not yet written."""
    stmt = select(MediaAssetModel.id).where(
        MediaAssetModel.run_id == run_id,
        MediaAssetModel.kind == "MANIFEST",
    )
    return session.execute(stmt).scalar_one_or_none()


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=RunAccepted)
def create_run(
    payload: RunCreate,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> RunAccepted:
    """Atomically enqueue analysis run and background job."""
    return enqueue_run(session, payload, settings)


@router.get("", response_model=list[RunDetail])
def get_runs(
    limit: int = Query(default=50, ge=1, le=100),
    video_id: str | None = Query(default=None),
    session: Session = Depends(get_db_session),
) -> list[RunDetail]:
    """List runs ordered by creation date descending."""
    runs = list_runs(session, limit=limit, video_id=video_id)
    out = []
    for r in runs:
        try:
            warnings = json.loads(r.warnings_json)
        except Exception:
            warnings = []

        manifest_media_id = _get_manifest_media_id(session, r.id) if r.status == "SUCCEEDED" else None
        manifest_url = f"/api/v1/media/{manifest_media_id}" if manifest_media_id else None

        out.append(
            RunDetail(
                id=r.id,
                video_id=r.video_id,
                camera_profile_id=r.camera_profile_id,
                camera_profile_version=r.camera_profile_version,
                mode=r.mode,  # type: ignore
                status=r.status,  # type: ignore
                model_backend=r.model_backend,
                rules_version=r.rules_version,
                risk_policy_version=r.risk_policy_version,
                warnings=warnings,
                manifest_url=manifest_url,
                created_at=r.created_at,
                started_at=r.started_at,
                finished_at=r.finished_at,
            )
        )
    return out


@router.get("/{run_id}", response_model=RunDetail)
def get_run_by_id(
    run_id: str,
    session: Session = Depends(get_db_session),
) -> RunDetail:
    """Retrieve run details by ID."""
    r = get_run(session, run_id)
    if not r:
        raise ProblemError(
            status_code=404,
            code="RUN_NOT_FOUND",
            title="Run not found",
            detail=f"Run with ID {run_id} was not found.",
        )

    try:
        warnings = json.loads(r.warnings_json)
    except Exception:
        warnings = []

    manifest_media_id = _get_manifest_media_id(session, r.id) if r.status == "SUCCEEDED" else None
    manifest_url = f"/api/v1/media/{manifest_media_id}" if manifest_media_id else None

    return RunDetail(
        id=r.id,
        video_id=r.video_id,
        camera_profile_id=r.camera_profile_id,
        camera_profile_version=r.camera_profile_version,
        mode=r.mode,  # type: ignore
        status=r.status,  # type: ignore
        model_backend=r.model_backend,
        rules_version=r.rules_version,
        risk_policy_version=r.risk_policy_version,
        warnings=warnings,
        manifest_url=manifest_url,
        created_at=r.created_at,
        started_at=r.started_at,
        finished_at=r.finished_at,
    )
