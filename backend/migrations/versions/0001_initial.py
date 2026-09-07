"""0001_initial

Revision ID: 0001_initial
Revises: 
Create Date: 2026-09-04 09:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. videos table
    op.execute("""
    CREATE TABLE videos (
      id TEXT PRIMARY KEY,
      original_name TEXT NOT NULL CHECK(length(original_name) BETWEEN 1 AND 255),
      sha256 TEXT NOT NULL CHECK(length(sha256)=64),
      size_bytes INTEGER NOT NULL CHECK(size_bytes > 0),
      duration_ms INTEGER NOT NULL CHECK(duration_ms > 0),
      width INTEGER NOT NULL CHECK(width > 0),
      height INTEGER NOT NULL CHECK(height > 0),
      fps REAL NOT NULL CHECK(fps > 0),
      created_at TEXT NOT NULL,
      expires_at TEXT NOT NULL
    );
    """)

    # 2. camera_profiles table
    op.execute("""
    CREATE TABLE camera_profiles (
      id TEXT NOT NULL,
      name TEXT NOT NULL,
      version INTEGER NOT NULL CHECK(version > 0),
      profile_json TEXT NOT NULL CHECK(json_valid(profile_json)),
      sha256 TEXT NOT NULL CHECK(length(sha256)=64),
      created_at TEXT NOT NULL,
      PRIMARY KEY(id, version)
    );
    """)

    # 3. runs table
    op.execute("""
    CREATE TABLE runs (
      id TEXT PRIMARY KEY,
      video_id TEXT NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
      camera_profile_id TEXT NOT NULL,
      camera_profile_version INTEGER NOT NULL,
      mode TEXT NOT NULL CHECK(mode IN ('LIVE','REPLAY')),
      status TEXT NOT NULL CHECK(status IN ('QUEUED','RUNNING','SUCCEEDED','FAILED')),
      model_backend TEXT NOT NULL,
      model_sha256 TEXT NOT NULL CHECK(length(model_sha256)=64),
      rules_version TEXT NOT NULL,
      risk_policy_version TEXT NOT NULL,
      warnings_json TEXT NOT NULL DEFAULT '[]' CHECK(json_valid(warnings_json)),
      error_code TEXT,
      error_detail TEXT,
      created_at TEXT NOT NULL,
      started_at TEXT,
      finished_at TEXT,
      FOREIGN KEY(camera_profile_id, camera_profile_version)
        REFERENCES camera_profiles(id, version)
    );
    """)

    # 4. jobs table
    op.execute("""
    CREATE TABLE jobs (
      id TEXT PRIMARY KEY,
      run_id TEXT NOT NULL UNIQUE REFERENCES runs(id) ON DELETE CASCADE,
      state TEXT NOT NULL CHECK(state IN ('QUEUED','RUNNING','SUCCEEDED','FAILED')),
      stage TEXT NOT NULL CHECK(stage IN ('QUEUED','NORMALIZING','DETECTING','VERIFYING','SCORING','WRITING_EVIDENCE','COMPLETE','FAILED')),
      progress INTEGER NOT NULL DEFAULT 0 CHECK(progress BETWEEN 0 AND 100),
      attempt INTEGER NOT NULL DEFAULT 0 CHECK(attempt >= 0),
      max_attempts INTEGER NOT NULL DEFAULT 2 CHECK(max_attempts BETWEEN 1 AND 5),
      leased_by TEXT,
      lease_expires_at TEXT,
      heartbeat_at TEXT,
      available_at TEXT NOT NULL,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );
    """)

    # 5. events table
    op.execute("""
    CREATE TABLE events (
      id TEXT PRIMARY KEY,
      run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
      event_type TEXT NOT NULL CHECK(event_type IN ('DROP','FORCEFUL_RELEASE','DRAGGING','VISIBLE_SUPPORT_OVERHANG','PROHIBITED_ZONE','STANDING_ON_PRODUCT')),
      start_ms INTEGER NOT NULL CHECK(start_ms >= 0),
      end_ms INTEGER NOT NULL CHECK(end_ms >= start_ms),
      primary_track_id INTEGER NOT NULL,
      risk_score INTEGER NOT NULL CHECK(risk_score BETWEEN 0 AND 100),
      risk_tier TEXT NOT NULL CHECK(risk_tier IN ('LOW','MEDIUM','HIGH','CRITICAL')),
      evidence_quality REAL NOT NULL CHECK(evidence_quality BETWEEN 0 AND 1),
      verification_status TEXT NOT NULL CHECK(verification_status IN ('NOT_RUN','PASSED','FAILED')),
      facts_json TEXT NOT NULL CHECK(json_valid(facts_json)),
      decision_trace_json TEXT NOT NULL CHECK(json_valid(decision_trace_json)),
      policy_sha256 TEXT NOT NULL CHECK(length(policy_sha256)=64),
      created_at TEXT NOT NULL,
      UNIQUE(run_id, event_type, primary_track_id, start_ms)
    );
    """)

    # 6. reviews table
    op.execute("""
    CREATE TABLE reviews (
      id TEXT PRIMARY KEY,
      event_id TEXT NOT NULL REFERENCES events(id) ON DELETE CASCADE,
      revision INTEGER NOT NULL CHECK(revision > 0),
      verdict TEXT NOT NULL CHECK(verdict IN ('CONFIRMED_RISK','REJECTED','UNCERTAIN')),
      note TEXT NOT NULL DEFAULT '' CHECK(length(note) <= 1000),
      reviewer_name TEXT NOT NULL CHECK(length(reviewer_name) BETWEEN 1 AND 100),
      created_at TEXT NOT NULL,
      UNIQUE(event_id, revision)
    );
    """)

    # 7. media_assets table
    op.execute("""
    CREATE TABLE media_assets (
      id TEXT PRIMARY KEY,
      video_id TEXT REFERENCES videos(id) ON DELETE CASCADE,
      run_id TEXT REFERENCES runs(id) ON DELETE CASCADE,
      event_id TEXT REFERENCES events(id) ON DELETE CASCADE,
      kind TEXT NOT NULL CHECK(kind IN ('SOURCE','NORMALIZED','ANNOTATED','TRACKS','EVENTS_JSON','MANIFEST','EVENT_CLIP','THUMBNAIL','TRACE')),
      relative_path TEXT NOT NULL UNIQUE,
      mime_type TEXT NOT NULL,
      size_bytes INTEGER NOT NULL CHECK(size_bytes >= 0),
      sha256 TEXT NOT NULL CHECK(length(sha256)=64),
      created_at TEXT NOT NULL,
      CHECK(video_id IS NOT NULL OR run_id IS NOT NULL OR event_id IS NOT NULL)
    );
    """)

    # 8. worker_locks table
    op.execute("""
    CREATE TABLE worker_locks (
      lock_name TEXT PRIMARY KEY CHECK(lock_name='video-worker'),
      owner_id TEXT NOT NULL,
      status TEXT NOT NULL CHECK(status IN ('STARTING','READY','BUSY','ERROR','STOPPING')),
      model_sha256 TEXT,
      error_code TEXT,
      heartbeat_at TEXT NOT NULL,
      expires_at TEXT NOT NULL
    );
    """)

    # Indexes
    op.execute("CREATE INDEX idx_runs_video_created ON runs(video_id, created_at DESC);")
    op.execute("CREATE INDEX idx_jobs_claim ON jobs(state, available_at, created_at);")
    op.execute("CREATE INDEX idx_events_run_time ON events(run_id, start_ms);")
    op.execute("CREATE INDEX idx_events_type_tier ON events(event_type, risk_tier);")
    op.execute("CREATE UNIQUE INDEX idx_one_source_per_video ON media_assets(video_id) WHERE kind='SOURCE';")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS worker_locks;")
    op.execute("DROP TABLE IF EXISTS media_assets;")
    op.execute("DROP TABLE IF EXISTS reviews;")
    op.execute("DROP TABLE IF EXISTS events;")
    op.execute("DROP TABLE IF EXISTS jobs;")
    op.execute("DROP TABLE IF EXISTS runs;")
    op.execute("DROP TABLE IF EXISTS camera_profiles;")
    op.execute("DROP TABLE IF EXISTS videos;")
