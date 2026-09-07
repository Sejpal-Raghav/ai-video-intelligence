"""Worker process mutual exclusion and heartbeat leasing matching Blueprint Section 14.3."""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from warehouse_ai.repositories.models import WorkerLockModel


class WorkerLockConflictError(Exception):
    """Raised when another active worker holds the application lock."""
    pass


class WorkerLostLeaseError(Exception):
    """Raised when the worker fails to update its lock heartbeat."""
    pass


class WorkerLeaseManager:
    """Manages the single-worker lock row in worker_locks table."""

    def __init__(self, session: Session, worker_id: str | None = None, lease_seconds: int = 60) -> None:
        self.session = session
        self.worker_id = worker_id or str(uuid.uuid4())
        self.lease_seconds = lease_seconds
        self.lock_name = "video-worker"

    def acquire_startup_lock(self, model_sha256: str | None = None) -> None:
        """Acquire or replace the worker lock at startup. Exits with code 2 if locked by another active worker."""
        now_utc = datetime.now(timezone.utc)
        now_iso = now_utc.isoformat()
        expires_iso = (now_utc + timedelta(seconds=self.lease_seconds)).isoformat()

        # Query existing lock
        stmt = select(WorkerLockModel).where(WorkerLockModel.lock_name == self.lock_name)
        existing = self.session.execute(stmt).scalar_one_or_none()

        if existing:
            if existing.expires_at > now_iso and existing.owner_id != self.worker_id:
                # Lock is actively held by another process -> exit with code 2 per Section 14.3
                raise WorkerLockConflictError(
                    f"Worker lock 'video-worker' is actively held by {existing.owner_id} until {existing.expires_at}"
                )
            # Expired or same owner: take ownership
            existing.owner_id = self.worker_id
            existing.status = "STARTING"
            existing.model_sha256 = model_sha256
            existing.error_code = None
            existing.heartbeat_at = now_iso
            existing.expires_at = expires_iso
        else:
            new_lock = WorkerLockModel(
                lock_name=self.lock_name,
                owner_id=self.worker_id,
                status="STARTING",
                model_sha256=model_sha256,
                error_code=None,
                heartbeat_at=now_iso,
                expires_at=expires_iso,
            )
            self.session.add(new_lock)

        self.session.commit()

    def set_status(self, status: str, error_code: str | None = None) -> None:
        """Update worker lock status (e.g. READY, BUSY, ERROR, STOPPING)."""
        now_utc = datetime.now(timezone.utc)
        now_iso = now_utc.isoformat()
        expires_iso = (now_utc + timedelta(seconds=self.lease_seconds)).isoformat()

        stmt = (
            update(WorkerLockModel)
            .where(
                WorkerLockModel.lock_name == self.lock_name,
                WorkerLockModel.owner_id == self.worker_id,
            )
            .values(
                status=status,
                error_code=error_code,
                heartbeat_at=now_iso,
                expires_at=expires_iso,
            )
        )
        res = self.session.execute(stmt)
        self.session.commit()
        if res.rowcount == 0:
            raise WorkerLostLeaseError("Worker lost lock ownership while changing status")

    def heartbeat(self) -> None:
        """Send 10-second heartbeat conditionally updating heartbeat_at and expires_at."""
        now_utc = datetime.now(timezone.utc)
        now_iso = now_utc.isoformat()
        expires_iso = (now_utc + timedelta(seconds=self.lease_seconds)).isoformat()

        stmt = (
            update(WorkerLockModel)
            .where(
                WorkerLockModel.lock_name == self.lock_name,
                WorkerLockModel.owner_id == self.worker_id,
            )
            .values(
                heartbeat_at=now_iso,
                expires_at=expires_iso,
            )
        )
        res = self.session.execute(stmt)
        self.session.commit()
        if res.rowcount == 0:
            raise WorkerLostLeaseError("Worker heartbeat failed: lost ownership of video-worker lock")

    def release_shutdown_lock(self) -> None:
        """Graceful shutdown: delete only its owned lock row."""
        try:
            stmt = delete(WorkerLockModel).where(
                WorkerLockModel.lock_name == self.lock_name,
                WorkerLockModel.owner_id == self.worker_id,
            )
            self.session.execute(stmt)
            self.session.commit()
        except Exception:
            self.session.rollback()
