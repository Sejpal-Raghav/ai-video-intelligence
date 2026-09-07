"""Job repository and atomic lease transitions matching Blueprint Section 14.3."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from warehouse_ai.repositories.models import JobModel, RunModel


def get_job(session: Session, job_id: str) -> JobModel | None:
    """Get job by ID."""
    stmt = select(JobModel).where(JobModel.id == job_id)
    return session.execute(stmt).scalar_one_or_none()


def get_job_by_run_id(session: Session, run_id: str) -> JobModel | None:
    """Get job by run ID."""
    stmt = select(JobModel).where(JobModel.run_id == run_id)
    return session.execute(stmt).scalar_one_or_none()


def insert_job(session: Session, job: JobModel) -> JobModel:
    """Insert a new job."""
    session.add(job)
    session.flush()
    return job


def claim_oldest_eligible_job(
    session: Session, worker_id: str, lease_seconds: int = 60
) -> JobModel | None:
    """Claim the oldest QUEUED job with available_at <= now.

    Uses conditional update to ensure only one worker claims the job.
    """
    now_utc = datetime.now(timezone.utc)
    now_iso = now_utc.isoformat()
    lease_expires = (now_utc + timedelta(seconds=lease_seconds)).isoformat()

    # Find oldest eligible queued job
    stmt = (
        select(JobModel)
        .where(
            JobModel.state == "QUEUED",
            JobModel.available_at <= now_iso,
        )
        .order_by(JobModel.created_at.asc())
        .limit(1)
    )
    job = session.execute(stmt).scalar_one_or_none()
    if not job:
        return None

    # Perform conditional update
    update_stmt = (
        update(JobModel)
        .where(
            JobModel.id == job.id,
            JobModel.state == "QUEUED",
        )
        .values(
            state="RUNNING",
            attempt=job.attempt + 1,
            leased_by=worker_id,
            heartbeat_at=now_iso,
            lease_expires_at=lease_expires,
            updated_at=now_iso,
        )
    )
    result = session.execute(update_stmt)
    if result.rowcount == 0:
        return None

    # Update corresponding run to RUNNING
    run_update = (
        update(RunModel)
        .where(RunModel.id == job.run_id)
        .values(status="RUNNING", started_at=now_iso)
    )
    session.execute(run_update)
    session.flush()

    return get_job(session, job.id)


def heartbeat_job(
    session: Session, job_id: str, worker_id: str, lease_seconds: int = 60
) -> bool:
    """Update job heartbeat and extend lease."""
    now_utc = datetime.now(timezone.utc)
    now_iso = now_utc.isoformat()
    lease_expires = (now_utc + timedelta(seconds=lease_seconds)).isoformat()

    stmt = (
        update(JobModel)
        .where(
            JobModel.id == job_id,
            JobModel.leased_by == worker_id,
            JobModel.state == "RUNNING",
        )
        .values(
            heartbeat_at=now_iso,
            lease_expires_at=lease_expires,
            updated_at=now_iso,
        )
    )
    res = session.execute(stmt)
    session.flush()
    return res.rowcount > 0


def update_job_progress(
    session: Session,
    job_id: str,
    worker_id: str,
    stage: str,
    progress: int,
) -> bool:
    """Update job stage and progress ensuring progress never decreases."""
    now_iso = datetime.now(timezone.utc).isoformat()
    stmt = (
        update(JobModel)
        .where(
            JobModel.id == job_id,
            JobModel.leased_by == worker_id,
            JobModel.state == "RUNNING",
            JobModel.progress <= progress,
        )
        .values(
            stage=stage,
            progress=progress,
            updated_at=now_iso,
        )
    )
    res = session.execute(stmt)
    session.flush()
    return res.rowcount > 0


def sweep_expired_jobs(session: Session) -> int:
    """Requeue or fail running jobs whose leases have expired."""
    now_iso = datetime.now(timezone.utc).isoformat()
    stmt = select(JobModel).where(
        JobModel.state == "RUNNING",
        JobModel.lease_expires_at <= now_iso,
    )
    expired_jobs = list(session.execute(stmt).scalars().all())
    count = len(expired_jobs)

    for job in expired_jobs:
        if job.attempt < job.max_attempts:
            # Requeue
            job.state = "QUEUED"
            job.stage = "QUEUED"
            job.progress = 0
            job.leased_by = None
            job.lease_expires_at = None
            job.updated_at = now_iso
            # Update run to QUEUED
            session.execute(
                update(RunModel)
                .where(RunModel.id == job.run_id)
                .values(status="QUEUED")
            )
        else:
            # Terminal fail
            job.state = "FAILED"
            job.stage = "FAILED"
            job.updated_at = now_iso
            session.execute(
                update(RunModel)
                .where(RunModel.id == job.run_id)
                .values(
                    status="FAILED",
                    error_code="LEASE_EXPIRED",
                    error_detail=f"Job exceeded max attempts ({job.max_attempts})",
                    finished_at=now_iso,
                )
            )

    session.flush()
    return count
