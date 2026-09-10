"""Service for enqueuing runs and jobs atomically matching Blueprint Section 14 & 15."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session

from warehouse_ai.api.errors import ProblemError
from warehouse_ai.api.schemas import RunAccepted, RunCreate
from warehouse_ai.config import Settings
from warehouse_ai.repositories.camera_profiles import get_camera_profile
from warehouse_ai.repositories.jobs import insert_job
from warehouse_ai.repositories.models import JobModel, RunModel, WorkerLockModel
from warehouse_ai.repositories.runs import insert_run
from warehouse_ai.repositories.videos import get_video


def enqueue_run(
    session: Session,
    payload: RunCreate,
    settings: Settings,
) -> RunAccepted:
    """Validate video, camera profile, worker health and atomically insert Run and Job."""
    # 1. Check video exists
    video = get_video(session, payload.video_id)
    if not video:
        raise ProblemError(
            status_code=404,
            code="VIDEO_NOT_FOUND",
            title="Video not found",
            detail=f"Video with ID {payload.video_id} does not exist.",
        )

    # 2. Check camera profile exists with exact id and version
    cam_profile = get_camera_profile(
        session, payload.camera_profile_id, payload.camera_profile_version
    )
    if not cam_profile:
        raise ProblemError(
            status_code=422,
            code="CALIBRATION_MISMATCH",
            title="Camera profile mismatch",
            detail=f"Camera profile '{payload.camera_profile_id}' version {payload.camera_profile_version} not found.",
        )

    # 3. Check worker lock status if in LIVE mode
    if payload.mode == "LIVE":
        worker_lock = session.execute(
            select(WorkerLockModel).where(WorkerLockModel.lock_name == "video-worker")
        ).scalar_one_or_none()
        if worker_lock and worker_lock.status == "ERROR":
            raise ProblemError(
                status_code=503,
                code="WORKER_UNAVAILABLE",
                title="Analysis worker unavailable",
                detail=f"Worker is in terminal ERROR state: {worker_lock.error_code or 'Unknown error'}",
            )

    run_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()

    # Model metadata: reflects whichever model vision/factory.py::build_detector_tracker
    # will actually load — the purpose-trained warehouse-v1 weights if present,
    # otherwise the yolo11n COCO-proxy fallback (see models/checksums.json).
    model_sha256 = "0" * 64
    checksums_file = settings.storage_root_path.parent / "models" / "checksums.json"
    if checksums_file.exists():
        try:
            chk = json.loads(checksums_file.read_text(encoding="utf-8"))
            models = chk.get("models", {})
            entry_key = "warehouse-v1" if settings.model_file_path.exists() else "yolo11n-coco-fallback"
            model_sha256 = models.get(entry_key, {}).get("weights_sha256", "0" * 64)
        except Exception:
            pass

    run = RunModel(
        id=run_id,
        video_id=payload.video_id,
        camera_profile_id=payload.camera_profile_id,
        camera_profile_version=payload.camera_profile_version,
        mode=payload.mode,
        status="QUEUED",
        model_backend=settings.MODEL_BACKEND.value,
        model_sha256=model_sha256,
        rules_version="v1",
        risk_policy_version="v1",
        warnings_json="[]",
        created_at=now_iso,
    )

    job = JobModel(
        id=job_id,
        run_id=run_id,
        state="QUEUED",
        stage="QUEUED",
        progress=0,
        attempt=0,
        max_attempts=settings.JOB_MAX_ATTEMPTS,
        available_at=now_iso,
        created_at=now_iso,
        updated_at=now_iso,
    )

    try:
        insert_run(session, run)
        insert_job(session, job)
        session.commit()
    except Exception as err:
        session.rollback()
        raise ProblemError(
            status_code=500,
            code="INTERNAL_ERROR",
            title="Failed to enqueue run",
            detail=f"Database transaction failed: {err}",
        ) from err

    return RunAccepted(
        run_id=run_id,
        job_id=job_id,
        status="QUEUED",
        status_url=f"/api/v1/jobs/{job_id}",
    )
