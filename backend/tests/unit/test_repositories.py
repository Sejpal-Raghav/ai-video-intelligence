"""Unit tests for repositories: videos, camera_profiles, runs, jobs, events, reviews, media."""

from datetime import datetime, timezone
import pytest
from sqlalchemy.orm import sessionmaker

from warehouse_ai.repositories.camera_profiles import (
    create_camera_profile_version,
    get_camera_profile,
    get_latest_camera_profile,
    list_camera_profiles,
)
from warehouse_ai.repositories.database import Base, init_db
from warehouse_ai.repositories.events import (
    decode_cursor,
    encode_cursor,
    get_event,
    insert_events,
    list_events,
)
from warehouse_ai.repositories.jobs import (
    claim_oldest_eligible_job,
    get_job,
    heartbeat_job,
    insert_job,
    sweep_expired_jobs,
    update_job_progress,
)
from warehouse_ai.repositories.media import (
    PathTraversalError,
    MediaNotFoundError,
    get_media_asset,
    insert_media_asset,
    resolve_media_path,
)
from warehouse_ai.repositories.models import (
    CameraProfileModel,
    EventModel,
    JobModel,
    MediaAssetModel,
    ReviewModel,
    RunModel,
    VideoModel,
)
from warehouse_ai.repositories.reviews import (
    append_review,
    get_latest_review,
    list_reviews_for_event,
)
from warehouse_ai.repositories.videos import (
    delete_video,
    get_video,
    insert_video,
    is_video_active,
)


@pytest.fixture
def session(tmp_path):
    db_file = tmp_path / "test_repos.db"
    engine = init_db(f"sqlite:///{db_file.as_posix()}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    sess = Session()
    yield sess
    sess.close()


def test_camera_profiles_immutable_versioning(session):
    # Version 1
    p1 = create_camera_profile_version(
        session, "cam-1", "Camera 1", '{"aspect": 1.77}', "a" * 64
    )
    session.commit()
    assert p1.version == 1

    # Version 2
    p2 = create_camera_profile_version(
        session, "cam-1", "Camera 1 Updated", '{"aspect": 1.77, "zoom": 1.2}', "b" * 64
    )
    session.commit()
    assert p2.version == 2

    # Query latest
    latest = get_latest_camera_profile(session, "cam-1")
    assert latest.version == 2
    assert latest.name == "Camera 1 Updated"

    # Query specific version
    v1 = get_camera_profile(session, "cam-1", 1)
    assert v1.version == 1
    assert v1.name == "Camera 1"

    # List profiles
    profiles = list_camera_profiles(session)
    assert len(profiles) == 1
    assert profiles[0].version == 2


def test_video_and_active_check(session):
    video = VideoModel(
        id="vid-1",
        original_name="test.mp4",
        sha256="a" * 64,
        size_bytes=1000,
        duration_ms=5000,
        width=1920,
        height=1080,
        fps=30.0,
        created_at=datetime.now(timezone.utc).isoformat(),
        expires_at=datetime.now(timezone.utc).isoformat(),
    )
    insert_video(session, video)
    session.commit()

    assert not is_video_active(session, "vid-1")

    # Add camera profile and active run
    create_camera_profile_version(session, "cam-1", "Cam 1", '{"poly":[]}', "c" * 64)
    run = RunModel(
        id="run-1",
        video_id="vid-1",
        camera_profile_id="cam-1",
        camera_profile_version=1,
        mode="LIVE",
        status="RUNNING",
        model_backend="ultralytics",
        model_sha256="d" * 64,
        rules_version="v1",
        risk_policy_version="v1",
        warnings_json="[]",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    session.add(run)
    session.commit()

    assert is_video_active(session, "vid-1")


def test_job_claim_heartbeat_and_progress(session):
    video = VideoModel(
        id="vid-job",
        original_name="job.mp4",
        sha256="e" * 64,
        size_bytes=100,
        duration_ms=1000,
        width=640,
        height=480,
        fps=25.0,
        created_at=datetime.now(timezone.utc).isoformat(),
        expires_at=datetime.now(timezone.utc).isoformat(),
    )
    insert_video(session, video)
    create_camera_profile_version(session, "cam-job", "Cam Job", '{}', "f" * 64)

    run = RunModel(
        id="run-job",
        video_id="vid-job",
        camera_profile_id="cam-job",
        camera_profile_version=1,
        mode="LIVE",
        status="QUEUED",
        model_backend="ultralytics",
        model_sha256="g" * 64,
        rules_version="v1",
        risk_policy_version="v1",
        warnings_json="[]",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    session.add(run)

    job = JobModel(
        id="job-1",
        run_id="run-job",
        state="QUEUED",
        stage="QUEUED",
        progress=0,
        attempt=0,
        max_attempts=2,
        available_at=datetime.now(timezone.utc).isoformat(),
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
    )
    insert_job(session, job)
    session.commit()

    # Claim job
    claimed = claim_oldest_eligible_job(session, worker_id="worker-test", lease_seconds=30)
    assert claimed is not None
    assert claimed.state == "RUNNING"
    assert claimed.attempt == 1
    assert claimed.leased_by == "worker-test"

    # Heartbeat
    hb_ok = heartbeat_job(session, "job-1", worker_id="worker-test", lease_seconds=60)
    assert hb_ok is True

    # Progress update
    prog_ok = update_job_progress(session, "job-1", "worker-test", stage="DETECTING", progress=30)
    assert prog_ok is True

    # Sweep should not affect non-expired job
    swept = sweep_expired_jobs(session)
    assert swept == 0


def test_cursor_pagination_and_event_filters(session):
    video = VideoModel(
        id="vid-evt",
        original_name="events.mp4",
        sha256="h" * 64,
        size_bytes=500,
        duration_ms=10000,
        width=1280,
        height=720,
        fps=30.0,
        created_at="2026-09-04T00:00:00Z",
        expires_at="2026-09-07T00:00:00Z",
    )
    insert_video(session, video)
    create_camera_profile_version(session, "cam-evt", "Cam Evt", '{}', "i" * 64)

    run = RunModel(
        id="run-evt",
        video_id="vid-evt",
        camera_profile_id="cam-evt",
        camera_profile_version=1,
        mode="LIVE",
        status="SUCCEEDED",
        model_backend="ultralytics",
        model_sha256="j" * 64,
        rules_version="v1",
        risk_policy_version="v1",
        warnings_json="[]",
        created_at="2026-09-04T00:00:00Z",
    )
    session.add(run)

    events = []
    for i in range(5):
        evt = EventModel(
            id=f"evt-{i}",
            run_id="run-evt",
            event_type="DROP" if i % 2 == 0 else "DRAGGING",
            start_ms=i * 1000,
            end_ms=(i * 1000) + 500,
            primary_track_id=1,
            risk_score=50 + (i * 10),
            risk_tier="MEDIUM" if i < 3 else "HIGH",
            evidence_quality=0.8,
            verification_status="PASSED",
            facts_json='{"val": 1}',
            decision_trace_json='{"predicates": []}',
            policy_sha256="k" * 64,
            created_at=f"2026-09-04T00:0{i}:00Z",
        )
        events.append(evt)

    insert_events(session, events)
    session.commit()

    # List all with limit 2 (first page)
    items1, cursor1 = list_events(session, run_id="run-evt", limit=2)
    assert len(items1) == 2
    assert cursor1 is not None

    # Second page
    items2, cursor2 = list_events(session, run_id="run-evt", limit=2, cursor=cursor1)
    assert len(items2) == 2
    assert items2[0].id != items1[0].id

    # Filter by risk tier
    highs, _ = list_events(session, run_id="run-evt", risk_tiers=["HIGH"])
    assert len(highs) == 2


def test_append_review_revisions(session):
    video = VideoModel(
        id="vid-rev",
        original_name="review.mp4",
        sha256="l" * 64,
        size_bytes=500,
        duration_ms=10000,
        width=1280,
        height=720,
        fps=30.0,
        created_at="2026-09-04T00:00:00Z",
        expires_at="2026-09-07T00:00:00Z",
    )
    insert_video(session, video)
    create_camera_profile_version(session, "cam-rev", "Cam", '{}', "m" * 64)

    run = RunModel(
        id="run-rev",
        video_id="vid-rev",
        camera_profile_id="cam-rev",
        camera_profile_version=1,
        mode="LIVE",
        status="SUCCEEDED",
        model_backend="ultralytics",
        model_sha256="n" * 64,
        rules_version="v1",
        risk_policy_version="v1",
        warnings_json="[]",
        created_at="2026-09-04T00:00:00Z",
    )
    session.add(run)

    event = EventModel(
        id="evt-rev-1",
        run_id="run-rev",
        event_type="DROP",
        start_ms=1000,
        end_ms=2000,
        primary_track_id=1,
        risk_score=75,
        risk_tier="HIGH",
        evidence_quality=0.9,
        verification_status="PASSED",
        facts_json='{}',
        decision_trace_json='{}',
        policy_sha256="o" * 64,
        created_at="2026-09-04T00:00:00Z",
    )
    session.add(event)
    session.commit()

    # Append revision 1
    r1 = append_review(session, "rev-1", "evt-rev-1", "CONFIRMED_RISK", "Reviewer 1", "Note 1")
    session.commit()
    assert r1.revision == 1

    # Append revision 2
    r2 = append_review(session, "rev-2", "evt-rev-1", "UNCERTAIN", "Reviewer 2", "Note 2")
    session.commit()
    assert r2.revision == 2

    latest = get_latest_review(session, "evt-rev-1")
    assert latest.revision == 2
    assert latest.verdict == "UNCERTAIN"

    all_revs = list_reviews_for_event(session, "evt-rev-1")
    assert len(all_revs) == 2


def test_media_path_resolution(tmp_path):
    storage_root = tmp_path / "storage"
    storage_root.mkdir()

    # Valid file
    media_file = storage_root / "videos" / "vid-1" / "source.mp4"
    media_file.parent.mkdir(parents=True)
    media_file.write_bytes(b"dummy")

    resolved = resolve_media_path("videos/vid-1/source.mp4", storage_root)
    assert resolved == media_file.resolve()

    # Traversal attempts
    with pytest.raises(PathTraversalError):
        resolve_media_path("../outside.mp4", storage_root)

    with pytest.raises(PathTraversalError):
        resolve_media_path("videos/../../outside.mp4", storage_root)

    # Missing file
    with pytest.raises(MediaNotFoundError):
        resolve_media_path("videos/nonexistent.mp4", storage_root)
