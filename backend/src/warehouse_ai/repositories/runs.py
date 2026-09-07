"""Run repository matching Blueprint Section 14 and Section 15."""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from warehouse_ai.repositories.models import RunModel


def get_run(session: Session, run_id: str) -> RunModel | None:
    """Fetch run by ID."""
    stmt = select(RunModel).where(RunModel.id == run_id)
    return session.execute(stmt).scalar_one_or_none()


def insert_run(session: Session, run: RunModel) -> RunModel:
    """Insert a new run."""
    session.add(run)
    session.flush()
    return run


def list_runs(
    session: Session, limit: int = 50, video_id: str | None = None
) -> list[RunModel]:
    """List recent runs ordered by created_at descending."""
    stmt = select(RunModel).order_by(RunModel.created_at.desc()).limit(limit)
    if video_id:
        stmt = stmt.where(RunModel.video_id == video_id)
    return list(session.execute(stmt).scalars().all())


def update_run_status(
    session: Session,
    run_id: str,
    status: str,
    started_at: str | None = None,
    finished_at: str | None = None,
    error_code: str | None = None,
    error_detail: str | None = None,
) -> None:
    """Update run status and diagnostic timestamps."""
    values: dict[str, object] = {"status": status}
    if started_at is not None:
        values["started_at"] = started_at
    if finished_at is not None:
        values["finished_at"] = finished_at
    if error_code is not None:
        values["error_code"] = error_code
    if error_detail is not None:
        values["error_detail"] = error_detail

    stmt = update(RunModel).where(RunModel.id == run_id).values(**values)
    session.execute(stmt)
    session.flush()
