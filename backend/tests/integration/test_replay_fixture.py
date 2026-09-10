"""Regression test for the real, non-mocked process_run() -> event path.

This is the checkpoint the original triage plan required ("a real video
produces event_count > 0") but which no test in the repository actually
exercised — every existing worker test injects an empty-result fake
pipeline. This test runs the genuine production code path (decode_frames ->
FrameSampler -> ReplayAdapter -> VisionPipeline -> RiskEngine ->
evidence/clips.py) against a real, checked-in demo clip and a real,
authored tracks.jsonl.gz fixture (see data/replay/README.md), with nothing
mocked except the two DB-only config loaders that would otherwise require
a repo-root-relative working directory during pytest collection.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from warehouse_ai.config import Settings
from warehouse_ai.repositories.database import Base, init_db
from warehouse_ai.repositories.models import (
    CameraProfileModel,
    EventModel,
    JobModel,
    MediaAssetModel,
    RunModel,
    VideoModel,
)
from warehouse_ai.worker.processor import process_run

REPO_ROOT = Path(__file__).resolve().parents[3]
DEMO_CLIP = REPO_ROOT / "data" / "replay" / "throwing-mattresses-demo-clip.mp4"
TRACKS_FIXTURE = REPO_ROOT / "data" / "replay" / "throwing-mattresses.tracks.jsonl.gz"


@pytest.mark.skipif(not DEMO_CLIP.exists(), reason="demo clip not present in this checkout")
@pytest.mark.skipif(not TRACKS_FIXTURE.exists(), reason="replay tracks fixture not present")
def test_replay_fixture_produces_real_event_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setenv("REPLAY_TRACKS_PATH", str(TRACKS_FIXTURE))

    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True)
    db_file = tmp_path / "replay_fixture.db"

    settings = Settings(
        DATABASE_URL=f"sqlite:///{db_file.as_posix()}",
        STORAGE_ROOT=str(storage_root),
        APP_ENV="test",
        MODEL_BACKEND="replay",
    )
    settings.storage_root_path = storage_root

    engine = init_db(f"sqlite:///{db_file.as_posix()}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    video_id, run_id, job_id = "vid-replay-fixture", "run-replay-fixture", "job-replay-fixture"

    source_dir = storage_root / "videos" / video_id
    source_dir.mkdir(parents=True)
    shutil.copy(DEMO_CLIP, source_dir / "source.mp4")

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,r_frame_rate",
         "-show_entries", "format=duration", "-of", "json", str(DEMO_CLIP)],
        capture_output=True, text=True, check=True,
    )
    meta = json.loads(probe.stdout)
    width = meta["streams"][0]["width"]
    height = meta["streams"][0]["height"]
    duration_ms = int(float(meta["format"]["duration"]) * 1000)
    num, den = meta["streams"][0]["r_frame_rate"].split("/")
    fps = float(num) / float(den)

    session.add(VideoModel(
        id=video_id, original_name="throwing-mattresses-demo-clip.mp4", sha256="1" * 64,
        size_bytes=DEMO_CLIP.stat().st_size, duration_ms=duration_ms,
        width=width, height=height, fps=fps,
        created_at="2026-09-10T00:00:00Z", expires_at="2026-09-13T00:00:00Z",
    ))
    session.add(CameraProfileModel(
        id="cam-replay-fixture", version=1, name="Replay Fixture Camera",
        profile_json=json.dumps({
            "schema_version": "camera-profile.v1", "id": "cam-replay-fixture",
            "name": "Replay Fixture Camera", "camera_motion": "FIXED",
            "frame_aspect_ratio": width / height,
            "floor_polygon": [[0.0, 0.5], [1.0, 0.5], [1.0, 1.0], [0.0, 1.0]],
            "zones": [], "support_regions": [], "created_at": "2026-09-10T00:00:00Z",
        }),
        sha256="2" * 64, created_at="2026-09-10T00:00:00Z",
    ))
    session.add(RunModel(
        id=run_id, video_id=video_id, camera_profile_id="cam-replay-fixture",
        camera_profile_version=1, mode="REPLAY", status="RUNNING",
        model_backend="replay", model_sha256="0" * 64,
        rules_version="v1", risk_policy_version="v1", warnings_json="[]",
        created_at="2026-09-10T00:00:00Z",
    ))
    job = JobModel(
        id=job_id, run_id=run_id, state="RUNNING", stage="QUEUED", progress=0,
        attempt=1, max_attempts=2, leased_by="test-worker",
        available_at="2026-09-10T00:00:00Z", created_at="2026-09-10T00:00:00Z",
        updated_at="2026-09-10T00:00:00Z",
    )
    session.add(job)
    session.commit()

    process_run(session=session, job=job, worker_id="test-worker", settings=settings)

    events = session.query(EventModel).filter_by(run_id=run_id).all()
    assert len(events) >= 1, "replay fixture must produce at least one real event"

    drop_events = [e for e in events if e.event_type == "DROP"]
    assert len(drop_events) == 1
    ev = drop_events[0]
    assert ev.risk_tier == "HIGH"
    assert ev.risk_score == 70
    assert ev.primary_track_id == 1

    assets = session.query(MediaAssetModel).filter_by(run_id=run_id).all()
    kinds = {a.kind for a in assets}
    assert "EVENT_CLIP" in kinds, "a real evidence clip must be generated for the event"
    assert "THUMBNAIL" in kinds

    clip_asset = next(a for a in assets if a.kind == "EVENT_CLIP")
    clip_path = storage_root / clip_asset.relative_path
    assert clip_path.exists()
    assert clip_asset.size_bytes > 0

    # The clip must be a real, decodable video file, not just bytes on disk.
    clip_probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", str(clip_path)],
        capture_output=True, text=True,
    )
    assert clip_probe.returncode == 0
    clip_meta = json.loads(clip_probe.stdout)
    assert float(clip_meta["format"]["duration"]) > 0

    session.close()
