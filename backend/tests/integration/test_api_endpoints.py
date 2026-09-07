"""Integration tests for all FastAPI endpoints, error formats, and media ranges."""

import io
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from warehouse_ai.api.app import create_app
from warehouse_ai.api.dependencies import get_app_settings, get_db_session
from warehouse_ai.config import Settings
from warehouse_ai.repositories.database import Base, init_db
from warehouse_ai.repositories.models import (
    CameraProfileModel,
    EventModel,
    MediaAssetModel,
    VideoModel,
)


@pytest.fixture
def client_and_session(tmp_path):
    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True)
    db_file = tmp_path / "test_api.db"

    test_settings = Settings(
        DATABASE_URL=f"sqlite:///{db_file.as_posix()}",
        STORAGE_ROOT=str(storage_root),
        APP_ENV="development",
    )
    test_settings.storage_root_path = storage_root

    engine = init_db(f"sqlite:///{db_file.as_posix()}")
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)

    def override_get_db():
        sess = TestingSession()
        try:
            yield sess
        finally:
            sess.close()

    app = create_app(test_settings)
    app.dependency_overrides[get_db_session] = override_get_db
    app.dependency_overrides[get_app_settings] = lambda: test_settings

    sess = TestingSession()
    client = TestClient(app)
    yield client, sess, storage_root
    sess.close()


def test_healthz(client_and_session):
    client, _, _ = client_and_session
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    assert resp.headers["X-Content-Type-Options"] == "nosniff"


def test_camera_profiles_crud(client_and_session):
    client, _, _ = client_and_session
    profile_payload = {
        "id": "demo-camera",
        "name": "Demo Camera Setup",
        "frame_aspect_ratio": 1.777778,
        "floor_polygon": [[0.02, 0.55], [0.98, 0.55], [0.98, 0.98], [0.02, 0.98]],
        "zones": [
            {
                "id": "loading",
                "kind": "ALLOWED",
                "severity": "NORMAL",
                "polygon": [[0.05, 0.60], [0.60, 0.60], [0.60, 0.95], [0.05, 0.95]],
            }
        ],
        "support_regions": [
            {
                "id": "pallet-1",
                "label": "Pallet 1 Top",
                "polygon": [[0.18, 0.62], [0.53, 0.60], [0.58, 0.83], [0.16, 0.85]],
            }
        ],
    }

    # Create profile
    resp = client.post("/api/v1/camera-profiles", json=profile_payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["id"] == "demo-camera"
    assert data["version"] == 1
    assert data["name"] == "Demo Camera Setup"
    assert "sha256" in data

    # Create version 2
    profile_payload["name"] = "Demo Camera Setup v2"
    resp2 = client.post("/api/v1/camera-profiles", json=profile_payload)
    assert resp2.status_code == 201
    assert resp2.json()["version"] == 2

    # List profiles
    list_resp = client.get("/api/v1/camera-profiles")
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert len(items) == 1
    assert items[0]["version"] == 2


def test_run_creation_and_job_polling(client_and_session):
    client, session, _ = client_and_session

    # Seed video
    video = VideoModel(
        id="vid-100",
        original_name="test.mp4",
        sha256="1" * 64,
        size_bytes=1024,
        duration_ms=5000,
        width=1920,
        height=1080,
        fps=30.0,
        created_at="2026-09-04T00:00:00Z",
        expires_at="2026-09-07T00:00:00Z",
    )
    session.add(video)

    # Seed camera profile
    cam = CameraProfileModel(
        id="demo-camera",
        version=1,
        name="Demo",
        profile_json='{"aspect": 1.77}',
        sha256="2" * 64,
        created_at="2026-09-04T00:00:00Z",
    )
    session.add(cam)
    session.commit()

    # Enqueue run
    run_payload = {
        "video_id": "vid-100",
        "camera_profile_id": "demo-camera",
        "camera_profile_version": 1,
        "mode": "LIVE",
    }
    resp = client.post("/api/v1/runs", json=run_payload)
    assert resp.status_code == 202
    run_data = resp.json()
    assert run_data["status"] == "QUEUED"
    job_id = run_data["job_id"]
    run_id = run_data["run_id"]

    # Poll job status
    job_resp = client.get(f"/api/v1/jobs/{job_id}")
    assert job_resp.status_code == 200
    job_data = job_resp.json()
    assert job_data["id"] == job_id
    assert job_data["state"] == "QUEUED"
    assert job_data["progress"] == 0

    # Query run detail
    run_resp = client.get(f"/api/v1/runs/{run_id}")
    assert run_resp.status_code == 200
    assert run_resp.json()["id"] == run_id


def test_events_and_reviews_workflow(client_and_session):
    client, session, _ = client_and_session

    # Seed video, profile, and run
    video = VideoModel(
        id="vid-200",
        original_name="test.mp4",
        sha256="3" * 64,
        size_bytes=1024,
        duration_ms=6000,
        width=1920,
        height=1080,
        fps=30.0,
        created_at="2026-09-04T00:00:00Z",
        expires_at="2026-09-07T00:00:00Z",
    )
    session.add(video)
    cam = CameraProfileModel(
        id="cam-200",
        version=1,
        name="Cam 200",
        profile_json='{}',
        sha256="4" * 64,
        created_at="2026-09-04T00:00:00Z",
    )
    session.add(cam)
    session.commit()

    run_payload = {
        "video_id": "vid-200",
        "camera_profile_id": "cam-200",
        "camera_profile_version": 1,
        "mode": "LIVE",
    }
    run_accepted = client.post("/api/v1/runs", json=run_payload).json()
    run_id = run_accepted["run_id"]

    # Seed event
    event = EventModel(
        id="evt-300",
        run_id=run_id,
        event_type="DROP",
        start_ms=1200,
        end_ms=2500,
        primary_track_id=4,
        risk_score=85,
        risk_tier="CRITICAL",
        evidence_quality=0.92,
        verification_status="PASSED",
        facts_json='{"downward_speed": 2.5, "zone": "edge"}',
        decision_trace_json='{"predicates": []}',
        policy_sha256="5" * 64,
        created_at="2026-09-04T08:00:00Z",
    )
    session.add(event)
    session.commit()

    # Query events list
    list_resp = client.get(f"/api/v1/events?run_id={run_id}")
    assert list_resp.status_code == 200
    page = list_resp.json()
    assert len(page["items"]) == 1
    assert page["items"][0]["id"] == "evt-300"
    assert page["items"][0]["risk"]["tier"] == "CRITICAL"
    assert page["items"][0]["review"] is None

    # Submit review
    review_payload = {
        "verdict": "CONFIRMED_RISK",
        "note": "Visible uncontrolled package impact.",
        "reviewer_name": "Auditor Bob",
    }
    rev_resp = client.post("/api/v1/events/evt-300/reviews", json=review_payload)
    assert rev_resp.status_code == 201
    rev_data = rev_resp.json()
    assert rev_data["revision"] == 1
    assert rev_data["verdict"] == "CONFIRMED_RISK"

    # Query event detail again -> latest review populated
    evt_resp = client.get("/api/v1/events/evt-300")
    assert evt_resp.status_code == 200
    evt_data = evt_resp.json()
    assert evt_data["review"] is not None
    assert evt_data["review"]["revision"] == 1
    assert evt_data["review"]["verdict"] == "CONFIRMED_RISK"


def test_media_streaming_with_ranges(client_and_session):
    client, session, storage_root = client_and_session

    # Write a test media file on disk
    rel_path = "videos/vid-media/source.mp4"
    disk_file = storage_root / rel_path
    disk_file.parent.mkdir(parents=True)
    content = b"0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    disk_file.write_bytes(content)

    video = VideoModel(
        id="vid-media",
        original_name="source.mp4",
        sha256="6" * 64,
        size_bytes=len(content),
        duration_ms=1000,
        width=640,
        height=480,
        fps=25.0,
        created_at="2026-09-04T00:00:00Z",
        expires_at="2026-09-07T00:00:00Z",
    )
    session.add(video)

    media = MediaAssetModel(
        id="media-400",
        video_id="vid-media",
        run_id=None,
        event_id=None,
        kind="SOURCE",
        relative_path=rel_path,
        mime_type="video/mp4",
        size_bytes=len(content),
        sha256="6" * 64,
        created_at="2026-09-04T00:00:00Z",
    )
    session.add(media)
    session.commit()

    # Full file request
    resp = client.get("/api/v1/media/media-400")
    assert resp.status_code == 200
    assert resp.content == content
    assert resp.headers["Accept-Ranges"] == "bytes"
    assert resp.headers["Content-Length"] == str(len(content))

    # Partial range request (bytes=0-9)
    resp_range = client.get("/api/v1/media/media-400", headers={"Range": "bytes=0-9"})
    assert resp_range.status_code == 206
    assert resp_range.content == b"0123456789"
    assert resp_range.headers["Content-Range"] == f"bytes 0-9/{len(content)}"
    assert resp_range.headers["Content-Length"] == "10"

    # Suffix range request (bytes=-10)
    resp_suffix = client.get("/api/v1/media/media-400", headers={"Range": "bytes=-10"})
    assert resp_suffix.status_code == 206
    assert resp_suffix.content == content[-10:]

    # Unsatisfiable range request
    resp_unsat = client.get("/api/v1/media/media-400", headers={"Range": "bytes=100-200"})
    assert resp_unsat.status_code == 416


def test_rfc7807_problem_json_errors(client_and_session):
    client, _, _ = client_and_session

    # 404 Video Not Found
    resp = client.get("/api/v1/videos/nonexistent-id")
    assert resp.status_code == 404
    assert resp.headers["content-type"] == "application/problem+json"
    data = resp.json()
    assert data["status"] == 404
    assert data["code"] == "VIDEO_NOT_FOUND"
    assert "request_id" in data
    assert "type" in data
