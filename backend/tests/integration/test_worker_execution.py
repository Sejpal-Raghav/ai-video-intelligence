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

    # Mock config loaders (avoid needing real YAML config files)
    from warehouse_ai.domain.models import (
        BehaviorRulesConfig, CommonRulesConfig, RelationshipRulesConfig,
        DropForcefulReleaseRulesConfig, DraggingRulesConfig, PlacementRulesConfig,
        StandingOnProductRulesConfig, RiskPolicyConfig,
    )
    from warehouse_ai.domain.models import CameraProfile

    dummy_rules = BehaviorRulesConfig(
        common=CommonRulesConfig(
            minimum_non_interpolated_observations=1,
            minimum_median_detection_confidence=0.1,
            minimum_track_coverage=0.0,
            maximum_interpolation_fraction=1.0,
            maximum_boundary_fraction=1.0,
            boundary_margin_norm=0.005,
            maximum_interpolation_gap_ms=200,
        ),
        relationships=RelationshipRulesConfig(
            near_package_diagonals=1.5,
            co_moving_minimum_speed_hps=0.1,
            co_moving_minimum_cosine=0.5,
            co_moving_minimum_ms=100,
            equipment_horizontal_overlap_ratio=0.5,
            equipment_top_tolerance_package_h=0.2,
            equipment_bottom_tolerance_package_h=0.1,
            floor_person_bottom_tolerance_person_h=0.1,
            visible_footprint_bottom_fraction=0.15,
        ),
        drop_forceful_release=DropForcefulReleaseRulesConfig(
            controlled_minimum_ms=300, release_minimum_ms=200, motion_window_ms=700,
            drop_minimum_displacement_h=0.5, drop_minimum_peak_down_speed_hps=1.25,
            forceful_minimum_horizontal_displacement_w=0.75, forceful_minimum_peak_horizontal_speed_hps=1.5,
            impact_maximum_ms_after_motion=1200, impact_minimum_pre_speed_hps=1.25,
            impact_maximum_post_speed_hps=0.35, impact_deceleration_window_ms=300,
            settle_maximum_speed_hps=0.25, settle_minimum_ms=400, settle_timeout_ms=1000, cooldown_ms=2000,
        ),
        dragging=DraggingRulesConfig(
            qualification_window_ms=800, minimum_horizontal_displacement_w=1.0,
            maximum_vertical_displacement_h=0.25, minimum_direction_agreement=0.7,
            direction_increment_deadband_w=0.02, minimum_direction_increments=3,
            active_minimum_horizontal_speed_hps=0.2, end_inactivity_ms=400, merge_gap_ms=500,
        ),
        placement=PlacementRulesConfig(
            stationary_maximum_speed_hps=0.25, prohibited_zone_dwell_ms=1000,
            prohibited_zone_exit_ms=500, minimum_visible_support_ratio=0.8,
            visible_support_dwell_ms=500, visible_support_exit_ms=500,
        ),
        standing_on_product=StandingOnProductRulesConfig(
            enabled=False, minimum_ankle_confidence=0.5, package_box_expansion_fraction=0.05,
            package_maximum_speed_hps=0.25, dwell_ms=1000, end_hysteresis_ms=300, merge_gap_ms=500,
        ),
    )
    dummy_risk_policy = RiskPolicyConfig(
        bases={"DROP": 45, "FORCEFUL_RELEASE": 55, "DRAGGING": 40, "VISIBLE_SUPPORT_OVERHANG": 35, "PROHIBITED_ZONE": 50, "STANDING_ON_PRODUCT": 45},
        tiers={"LOW": (0, 39), "MEDIUM": (40, 59), "HIGH": (60, 79), "CRITICAL": (80, 100)},
        zone_bonus={"NORMAL": 0, "SENSITIVE": 10, "CRITICAL": 20},
    )
    dummy_camera = CameraProfile(
        id="cam-work", name="Camera",
        frame_aspect_ratio=1.778,
        floor_polygon=[(0.0, 0.5), (1.0, 0.5), (1.0, 1.0), (0.0, 1.0)],
        created_at="2026-09-04T00:00:00Z",
    )

    monkeypatch.setattr("warehouse_ai.worker.processor._load_behavior_rules", lambda: dummy_rules)
    monkeypatch.setattr("warehouse_ai.worker.processor._load_risk_policy", lambda: dummy_risk_policy)
    monkeypatch.setattr("warehouse_ai.worker.processor._load_camera_profile", lambda *a, **kw: dummy_camera)

    # Use pipeline injection (the contract preserved in process_run) instead of
    # monkeypatching decode_frames + build_detector_tracker separately.
    # This is exactly the pattern the plan specifies tests should use.
    from warehouse_ai.vision.pipeline import VisionPipeline, VisionPipelineResult
    from typing import Any, Sequence

    class FakeVisionPipeline:
        """Returns empty results for integration test without real video."""
        def run(self, frames: Any, expected_total_frames: Any = None) -> VisionPipelineResult:
            return VisionPipelineResult()

    # Process run with injected pipeline (exercises all other stages)
    process_run(
        session=session,
        job=job,
        worker_id="worker-test",
        settings=settings,
        pipeline=FakeVisionPipeline(),  # type: ignore[arg-type]
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
