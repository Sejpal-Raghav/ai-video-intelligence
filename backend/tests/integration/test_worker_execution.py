"""Integration tests for worker leasing, end-to-end execution, and atomic publication."""

import json
import pytest
from sqlalchemy.orm import sessionmaker

from warehouse_ai.config import Settings
from warehouse_ai.repositories.database import Base, init_db
from warehouse_ai.repositories.models import (
    CameraProfileModel,
    JobModel,
    MediaAssetModel,
    RunModel,
    VideoModel,
    WorkerLockModel,
)
from warehouse_ai.worker.lease import (
    WorkerLeaseManager,
    WorkerLockConflictError,
)
from warehouse_ai.worker.processor import process_run


@pytest.fixture
def worker_context(tmp_path):
    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True)
    db_file = tmp_path / "test_worker.db"

    test_settings = Settings(
        DATABASE_URL=f"sqlite:///{db_file.as_posix()}",
        STORAGE_ROOT=str(storage_root),
        APP_ENV="test",
    )
    test_settings.storage_root_path = storage_root

    engine = init_db(f"sqlite:///{db_file.as_posix()}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    yield session, test_settings, storage_root
    session.close()


def test_worker_lease_mutual_exclusion(worker_context):
    session, _, _ = worker_context

    manager1 = WorkerLeaseManager(session, worker_id="worker-1", lease_seconds=60)
    manager1.acquire_startup_lock()

    # Second worker should fail because lock is active
    manager2 = WorkerLeaseManager(session, worker_id="worker-2", lease_seconds=60)
    with pytest.raises(WorkerLockConflictError):
        manager2.acquire_startup_lock()

    # Heartbeat and status update
    manager1.set_status("READY")
    lock_row = session.query(WorkerLockModel).filter_by(lock_name="video-worker").first()
    assert lock_row.status == "READY"
    assert lock_row.owner_id == "worker-1"

    # Graceful release
    manager1.release_shutdown_lock()
    assert session.query(WorkerLockModel).filter_by(lock_name="video-worker").first() is None


def test_worker_process_run_end_to_end(worker_context, monkeypatch):
    session, settings, storage_root = worker_context

    # Create dummy source video
    source_dir = storage_root / "videos" / "vid-work"
    source_dir.mkdir(parents=True)
    source_file = source_dir / "source.mp4"
    source_file.write_bytes(b"dummy-source-video-content")

    video = VideoModel(
        id="vid-work",
        original_name="source.mp4",
        sha256="1" * 64,
        size_bytes=len(b"dummy-source-video-content"),
        duration_ms=5000,
        width=1280,
        height=720,
        fps=25.0,
        created_at="2026-09-04T00:00:00Z",
        expires_at="2026-09-07T00:00:00Z",
    )
    session.add(video)

    cam = CameraProfileModel(
        id="cam-work",
        version=1,
        name="Camera",
        profile_json='{}',
        sha256="2" * 64,
        created_at="2026-09-04T00:00:00Z",
    )
    session.add(cam)

    run = RunModel(
        id="run-work",
        video_id="vid-work",
        camera_profile_id="cam-work",
        camera_profile_version=1,
        mode="LIVE",
        status="RUNNING",
        model_backend="ultralytics",
        model_sha256="3" * 64,
        rules_version="v1",
        risk_policy_version="v1",
        warnings_json="[]",
        created_at="2026-09-04T00:00:00Z",
    )
    session.add(run)

    job = JobModel(
        id="job-work",
        run_id="run-work",
        state="RUNNING",
        stage="QUEUED",
        progress=0,
        attempt=1,
        max_attempts=2,
        leased_by="worker-test",
        available_at="2026-09-04T00:00:00Z",
        created_at="2026-09-04T00:00:00Z",
        updated_at="2026-09-04T00:00:00Z",
    )
    session.add(job)
    session.commit()

    # Mock normalize_video to avoid requiring actual video frames for synthetic test
    from warehouse_ai.evidence.normalization import NormalizedMediaResult
    def fake_normalize(ffmpeg_path, source_path, output_path, source_fps, timeout_seconds=180):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"normalized-bytes")
        return NormalizedMediaResult(
            path=output_path,
            sha256="4" * 64,
            size_bytes=16,
            duration_ms=5000,
            fps=25.0,
            width=1280,
            height=720,
        )

    monkeypatch.setattr("warehouse_ai.worker.processor.normalize_video", fake_normalize)

    # Process run
    process_run(
        session=session,
        job=job,
        worker_id="worker-test",
        settings=settings,
    )

    # Verify atomic publication
    final_dir = storage_root / "runs" / "run-work"
    assert final_dir.exists()
    assert (final_dir / "normalized.mp4").exists()
    assert (final_dir / "tracks.jsonl.gz").exists()
    assert (final_dir / "events.json").exists()
    assert (final_dir / "manifest.json").exists()

    # Verify manifest content
    manifest_obj = json.loads((final_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest_obj["schema_version"] == "run-manifest.v1"
    assert manifest_obj["run_id"] == "run-work"

    # Verify Database records
    updated_job = session.query(JobModel).filter_by(id="job-work").first()
    assert updated_job.state == "SUCCEEDED"
    assert updated_job.stage == "COMPLETE"
    assert updated_job.progress == 100

    updated_run = session.query(RunModel).filter_by(id="run-work").first()
    assert updated_run.status == "SUCCEEDED"
    assert updated_run.finished_at is not None

    # Check media assets inserted
    assets = session.query(MediaAssetModel).filter_by(run_id="run-work").all()
    kinds = {a.kind for a in assets}
    assert "NORMALIZED" in kinds
    assert "TRACKS" in kinds
    assert "EVENTS_JSON" in kinds
    assert "MANIFEST" in kinds
