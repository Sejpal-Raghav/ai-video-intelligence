"""Job polling and status endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from warehouse_ai.api.dependencies import get_db_session
from warehouse_ai.api.errors import ProblemError
from warehouse_ai.api.schemas import JobStatusResponse
from warehouse_ai.repositories.jobs import get_job, get_job_by_run_id
from warehouse_ai.repositories.runs import get_run

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobStatusResponse)
def get_job_status(
    job_id: str,
    session: Session = Depends(get_db_session),
) -> JobStatusResponse:
    """Retrieve current background job progress and state."""
    job = get_job(session, job_id) or get_job_by_run_id(session, job_id)
    if not job:
        raise ProblemError(
            status_code=404,
            code="JOB_NOT_FOUND",
            title="Job not found",
            detail=f"Job with ID {job_id} was not found.",
        )

    err_dict = None
    if job.state == "FAILED":
        run = get_run(session, job.run_id)
        if run and run.error_code:
            err_dict = {"code": run.error_code, "detail": run.error_detail or ""}
        else:
            err_dict = {"code": "JOB_FAILED", "detail": "Background job failed unexpectedly."}

    return JobStatusResponse(
        id=job.id,
        run_id=job.run_id,
        state=job.state,  # type: ignore
        stage=job.stage,  # type: ignore
        progress=job.progress,
        attempt=job.attempt,
        updated_at=job.updated_at,
        error=err_dict,
    )
