"""Unit tests for video upload validation, probe parsing, and retention quarantine."""

import io
from pathlib import Path
import pytest
from sqlalchemy.orm import sessionmaker

from warehouse_ai.config import Settings
from warehouse_ai.repositories.database import Base, init_db
from warehouse_ai.repositories.models import RunModel, VideoModel
from warehouse_ai.services.ingest import (
    VideoValidationError,
    check_isobmff_ftyp_box,
    validate_probe_data,
)
from warehouse_ai.services.retention import (
    VideoActiveConflictError,
    delete_video_with_quarantine,
    purge_staging,
)


def test_ftyp_box_verification(tmp_path):
    # Valid MP4 header (size=32, ftyp, major_brand=isom)
    valid_header = b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2avc1mp41"
    valid_file = tmp_path / "valid.mp4"
    valid_file.write_bytes(valid_header)
    assert check_isobmff_ftyp_box(valid_file) is True

    # Invalid header (e.g. text/plain or corrupt)
    invalid_file = tmp_path / "invalid.mp4"
    invalid_file.write_bytes(b"RIFF\x00\x00\x00\x00WAVEfmt ")
    assert check_isobmff_ftyp_box(invalid_file) is False

    # Truncated header
    short_file = tmp_path / "short.mp4"
    short_file.write_bytes(b"\x00\x00")
    assert check_isobmff_ftyp_box(short_file) is False


def test_probe_data_validation():
    settings = Settings()

    # Valid probe data
    valid_probe = {
        "format": {"format_name": "mov,mp4,m4a,3gp,3g2,mj2", "duration": "12.500000"},
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1920,
                "height": 1080,
                "r_frame_rate": "30/1",
            },
            {"codec_type": "audio", "codec_name": "aac"},
        ],
    }
    meta = validate_probe_data(valid_probe, settings)
    assert meta.duration_ms == 12500
    assert meta.width == 1920
    assert meta.height == 1080
    assert meta.fps == 30.0
    assert meta.video_codec == "h264"

    # Invalid format name
    invalid_format = {
        "format": {"format_name": "matroska,webm", "duration": "10.0"},
        "streams": [{"codec_type": "video", "codec_name": "h264", "width": 1280, "height": 720, "r_frame_rate": "25/1"}],
    }
    with pytest.raises(VideoValidationError) as exc:
        validate_probe_data(invalid_format, settings)
    assert exc.value.code == "UNSUPPORTED_MEDIA"

    # Non-H264 codec
    hevc_probe = {
        "format": {"format_name": "mp4", "duration": "10.0"},
        "streams": [{"codec_type": "video", "codec_name": "hevc", "width": 1280, "height": 720, "r_frame_rate": "25/1"}],
    }
    with pytest.raises(VideoValidationError) as exc:
        validate_probe_data(hevc_probe, settings)
    assert exc.value.code == "UNSUPPORTED_MEDIA"

    # Excessive duration (>600s)
    long_probe = {
        "format": {"format_name": "mp4", "duration": "601.0"},
        "streams": [{"codec_type": "video", "codec_name": "h264", "width": 1280, "height": 720, "r_frame_rate": "25/1"}],
    }
    with pytest.raises(VideoValidationError) as exc:
        validate_probe_data(long_probe, settings)
    assert exc.value.code == "VIDEO_LIMIT_EXCEEDED"

    # Zero duration
    zero_probe = {
        "format": {"format_name": "mp4", "duration": "0.0"},
        "streams": [{"codec_type": "video", "codec_name": "h264", "width": 1280, "height": 720, "r_frame_rate": "25/1"}],
    }
    with pytest.raises(VideoValidationError) as exc:
        validate_probe_data(zero_probe, settings)
    assert exc.value.code == "VIDEO_LIMIT_EXCEEDED"

    # Excessive dimensions (>3840x2160)
    huge_probe = {
        "format": {"format_name": "mp4", "duration": "10.0"},
        "streams": [{"codec_type": "video", "codec_name": "h264", "width": 4096, "height": 2160, "r_frame_rate": "25/1"}],
    }
    with pytest.raises(VideoValidationError) as exc:
        validate_probe_data(huge_probe, settings)
    assert exc.value.code == "VIDEO_LIMIT_EXCEEDED"

    # Excessive frame rate (>60 fps)
    high_fps_probe = {
        "format": {"format_name": "mp4", "duration": "10.0"},
        "streams": [{"codec_type": "video", "codec_name": "h264", "width": 1280, "height": 720, "r_frame_rate": "120/1"}],
    }
    with pytest.raises(VideoValidationError) as exc:
        validate_probe_data(high_fps_probe, settings)
    assert exc.value.code == "VIDEO_LIMIT_EXCEEDED"


def test_delete_video_with_quarantine(tmp_path):
    db_file = tmp_path / "test_del.db"
    engine = init_db(f"sqlite:///{db_file.as_posix()}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    storage_root = tmp_path / "storage"
    storage_root.mkdir()

    # Create video row & file
    video_dir = storage_root / "videos" / "vid-del"
    video_dir.mkdir(parents=True)
    (video_dir / "source.mp4").write_bytes(b"content")

    video = VideoModel(
        id="vid-del",
        original_name="del.mp4",
        sha256="z" * 64,
        size_bytes=7,
        duration_ms=1000,
        width=1280,
        height=720,
        fps=25.0,
        created_at="2026-09-04T00:00:00Z",
        expires_at="2026-09-07T00:00:00Z",
    )
    session.add(video)
    session.commit()

    # Delete video
    ok = delete_video_with_quarantine(session, "vid-del", storage_root)
    assert ok is True
    assert not video_dir.exists()
    assert session.query(VideoModel).filter_by(id="vid-del").first() is None

    session.close()


def test_delete_video_conflict_when_active(tmp_path):
    db_file = tmp_path / "test_conflict.db"
    engine = init_db(f"sqlite:///{db_file.as_posix()}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    storage_root = tmp_path / "storage"
    storage_root.mkdir()

    video = VideoModel(
        id="vid-act",
        original_name="act.mp4",
        sha256="y" * 64,
        size_bytes=10,
        duration_ms=2000,
        width=1280,
        height=720,
        fps=25.0,
        created_at="2026-09-04T00:00:00Z",
        expires_at="2026-09-07T00:00:00Z",
    )
    session.add(video)

    from warehouse_ai.repositories.camera_profiles import create_camera_profile_version
    create_camera_profile_version(session, "cam-act", "Cam", '{}', "x" * 64)

    run = RunModel(
        id="run-act",
        video_id="vid-act",
        camera_profile_id="cam-act",
        camera_profile_version=1,
        mode="LIVE",
        status="RUNNING",
        model_backend="ultralytics",
        model_sha256="w" * 64,
        rules_version="v1",
        risk_policy_version="v1",
        warnings_json="[]",
        created_at="2026-09-04T00:00:00Z",
    )
    session.add(run)
    session.commit()

    with pytest.raises(VideoActiveConflictError):
        delete_video_with_quarantine(session, "vid-act", storage_root)

    session.close()
