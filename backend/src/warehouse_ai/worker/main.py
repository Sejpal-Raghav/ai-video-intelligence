"""Worker entrypoint and lifecycle loop matching Blueprint Section 14.3."""

from __future__ import annotations

import signal
import sys
import time
import uuid
from typing import Any

from warehouse_ai.config import get_settings
from warehouse_ai.logging import get_logger, setup_logging
from warehouse_ai.repositories.database import init_db
from warehouse_ai.repositories.jobs import claim_oldest_eligible_job, sweep_expired_jobs
from warehouse_ai.worker.lease import WorkerLeaseManager, WorkerLockConflictError, WorkerLostLeaseError
from warehouse_ai.worker.processor import process_run

logger = get_logger("warehouse_ai.worker")


class WorkerProcess:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.engine = init_db()
        self.worker_id = f"worker-{uuid.uuid4().hex[:8]}"
        self.running = True

    def run(self) -> None:
        setup_logging(self.settings.LOG_LEVEL)
        logger.info(f"Starting analysis worker {self.worker_id}")

        # Setup graceful signal handlers
        def handle_signal(signum: int, frame: Any) -> None:
            logger.info("Received termination signal; shutting down gracefully...")
            self.running = False

        try:
            signal.signal(signal.SIGINT, handle_signal)
            signal.signal(signal.SIGTERM, handle_signal)
        except ValueError:
            pass  # Non-main thread or unsupported platform

        from sqlalchemy.orm import sessionmaker
        SessionFactory = sessionmaker(bind=self.engine)
        session = SessionFactory()

        lease_manager = WorkerLeaseManager(
            session=session,
            worker_id=self.worker_id,
            lease_seconds=self.settings.JOB_LEASE_SECONDS,
        )

        try:
            lease_manager.acquire_startup_lock()
        except WorkerLockConflictError as err:
            logger.error(f"Cannot start worker: {err}")
            sys.exit(2)

        # Initial sweep of expired jobs on startup per Section 14.3
        sweep_expired_jobs(session)
        session.commit()

        lease_manager.set_status("READY")
        logger.info("Worker is READY for job leasing")

        last_heartbeat = time.time()
        last_sweep = time.time()

        try:
            while self.running:
                now = time.time()

                # Heartbeat every 10 seconds per Section 14.3
                if now - last_heartbeat >= self.settings.JOB_HEARTBEAT_SECONDS:
                    try:
                        lease_manager.heartbeat()
                        last_heartbeat = now
                    except WorkerLostLeaseError as err:
                        logger.error(f"Terminating: {err}")
                        break

                # Expired jobs sweep every 30 seconds
                if now - last_sweep >= 30.0:
                    sweep_expired_jobs(session)
                    session.commit()
                    last_sweep = now

                # Try to claim oldest eligible job
                job = claim_oldest_eligible_job(
                    session=session,
                    worker_id=self.worker_id,
                    lease_seconds=self.settings.JOB_LEASE_SECONDS,
                )

                if job:
                    logger.info(f"Claimed job {job.id} for run {job.run_id}")
                    lease_manager.set_status("BUSY")
                    try:
                        process_run(
                            session=session,
                            job=job,
                            worker_id=self.worker_id,
                            settings=self.settings,
                        )
                        logger.info(f"Successfully finished job {job.id}")
                    except Exception as err:
                        logger.error(f"Failed processing job {job.id}: {err}")
                    finally:
                        lease_manager.set_status("READY")

                time.sleep(1.0)

        finally:
            logger.info("Releasing worker lock...")
            lease_manager.release_shutdown_lock()
            session.close()
            logger.info("Worker stopped.")


def main() -> None:
    worker = WorkerProcess()
    worker.run()


if __name__ == "__main__":
    main()
