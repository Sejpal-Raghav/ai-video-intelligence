"""Tests for database engine pragmas, schema models, and constraints."""

import sqlite3
import pytest
from sqlalchemy import text
from warehouse_ai.repositories.database import Base, get_engine, init_db
from warehouse_ai.repositories.models import (
    CameraProfileModel,
    EventModel,
    JobModel,
    MediaAssetModel,
    ReviewModel,
    RunModel,
    VideoModel,
    WorkerLockModel,
)


def test_sqlite_pragmas(tmp_path):
    db_file = tmp_path / "test.db"
    engine = get_engine(f"sqlite:///{db_file}")

    with engine.connect() as conn:
        fk = conn.execute(text("PRAGMA foreign_keys;")).scalar()
        assert fk == 1

        journal = conn.execute(text("PRAGMA journal_mode;")).scalar()
        assert journal.lower() == "wal"

        sync = conn.execute(text("PRAGMA synchronous;")).scalar()
        # NORMAL in SQLite is 1
        assert sync == 1

        busy = conn.execute(text("PRAGMA busy_timeout;")).scalar()
        assert busy == 5000


def test_table_creation_and_constraints(tmp_path):
    db_file = tmp_path / "test_models.db"
    engine = init_db(f"sqlite:///{db_file}")
    Base.metadata.create_all(engine)

    with engine.connect() as conn:
        # Check all expected tables exist
        tables = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table';")
        ).scalars().all()

        expected = [
            "videos",
            "camera_profiles",
            "runs",
            "jobs",
            "events",
            "reviews",
            "media_assets",
            "worker_locks",
        ]
        for t in expected:
            assert t in tables


def test_video_and_run_foreign_key_cascade(tmp_path):
    db_file = tmp_path / "test_fk.db"
    engine = init_db(f"sqlite:///{db_file}")
    Base.metadata.create_all(engine)

    from sqlalchemy.orm import sessionmaker
    Session = sessionmaker(bind=engine)
    session = Session()

    # Create video
    video = VideoModel(
        id="vid-1",
        original_name="test.mp4",
        sha256="a" * 64,
        size_bytes=1024,
        duration_ms=5000,
        width=1920,
        height=1080,
        fps=30.0,
        created_at="2026-09-04T00:00:00Z",
        expires_at="2026-09-07T00:00:00Z",
    )
    session.add(video)

    # Create camera profile
    cam = CameraProfileModel(
        id="demo-camera",
        version=1,
        name="Demo",
        profile_json='{"aspect": 1.77}',
        sha256="b" * 64,
        created_at="2026-09-04T00:00:00Z",
    )
    session.add(cam)
    session.commit()

    # Create run
    run = RunModel(
        id="run-1",
        video_id="vid-1",
        camera_profile_id="demo-camera",
        camera_profile_version=1,
        mode="LIVE",
        status="QUEUED",
        model_backend="ultralytics",
        model_sha256="c" * 64,
        rules_version="v1",
        risk_policy_version="v1",
        warnings_json="[]",
        created_at="2026-09-04T00:00:00Z",
    )
    session.add(run)
    session.commit()

    # Verify run exists
    assert session.query(RunModel).filter_by(id="run-1").first() is not None

    # Delete video -> run should cascade delete
    session.delete(video)
    session.commit()

    assert session.query(RunModel).filter_by(id="run-1").first() is None
    session.close()


def test_alembic_migration(tmp_path):
    from alembic.config import Config
    from alembic import command
    from warehouse_ai.config import REPO_ROOT

    db_file = tmp_path / "alembic_test.db"
    ini_path = str(REPO_ROOT / "backend" / "alembic.ini")
    alembic_cfg = Config(ini_path)
    alembic_cfg.set_main_option("script_location", str(REPO_ROOT / "backend" / "migrations"))
    alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_file.as_posix()}")

    # Upgrade to head
    command.upgrade(alembic_cfg, "head")

    engine = get_engine(f"sqlite:///{db_file.as_posix()}")
    with engine.connect() as conn:
        tables = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table';")
        ).scalars().all()
        assert "alembic_version" in tables
        assert "videos" in tables
        assert "camera_profiles" in tables
        assert "runs" in tables
        assert "jobs" in tables
        assert "events" in tables
        assert "reviews" in tables
        assert "media_assets" in tables
        assert "worker_locks" in tables

    # Downgrade to base
    command.downgrade(alembic_cfg, "base")
    with engine.connect() as conn:
        tables = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table';")
        ).scalars().all()
        assert "videos" not in tables
        assert "runs" not in tables

