"""SQLAlchemy declarative models for authoritative schema matching Blueprint Section 14.2."""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from warehouse_ai.repositories.database import Base


class VideoModel(Base):
    __tablename__ = "videos"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    original_name: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    fps: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        CheckConstraint("length(original_name) BETWEEN 1 AND 255", name="ck_video_original_name_len"),
        CheckConstraint("length(sha256) = 64", name="ck_video_sha256_len"),
        CheckConstraint("size_bytes > 0", name="ck_video_size_bytes_gt0"),
        CheckConstraint("duration_ms > 0", name="ck_video_duration_ms_gt0"),
        CheckConstraint("width > 0", name="ck_video_width_gt0"),
        CheckConstraint("height > 0", name="ck_video_height_gt0"),
        CheckConstraint("fps > 0", name="ck_video_fps_gt0"),
    )

    runs: Mapped[list[RunModel]] = relationship(
        "RunModel", back_populates="video", cascade="all, delete-orphan"
    )
    media_assets: Mapped[list[MediaAssetModel]] = relationship(
        "MediaAssetModel", back_populates="video", cascade="all, delete-orphan"
    )


class CameraProfileModel(Base):
    __tablename__ = "camera_profiles"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    profile_json: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        CheckConstraint("version > 0", name="ck_camera_profile_version_gt0"),
        CheckConstraint("length(sha256) = 64", name="ck_camera_profile_sha256_len"),
        CheckConstraint("json_valid(profile_json)", name="ck_camera_profile_json_valid"),
    )

    runs: Mapped[list[RunModel]] = relationship("RunModel", back_populates="camera_profile")


class RunModel(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    video_id: Mapped[str] = mapped_column(
        Text, ForeignKey("videos.id", ondelete="CASCADE"), nullable=False
    )
    camera_profile_id: Mapped[str] = mapped_column(Text, nullable=False)
    camera_profile_version: Mapped[int] = mapped_column(Integer, nullable=False)
    mode: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    model_backend: Mapped[str] = mapped_column(Text, nullable=False)
    model_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    rules_version: Mapped[str] = mapped_column(Text, nullable=False)
    risk_policy_version: Mapped[str] = mapped_column(Text, nullable=False)
    warnings_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    finished_at: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        ForeignKeyConstraint(
            ["camera_profile_id", "camera_profile_version"],
            ["camera_profiles.id", "camera_profiles.version"],
            name="fk_runs_camera_profile",
        ),
        CheckConstraint("mode IN ('LIVE','REPLAY')", name="ck_run_mode"),
        CheckConstraint("status IN ('QUEUED','RUNNING','SUCCEEDED','FAILED')", name="ck_run_status"),
        CheckConstraint("length(model_sha256) = 64", name="ck_run_model_sha256_len"),
        CheckConstraint("json_valid(warnings_json)", name="ck_run_warnings_json_valid"),
        Index("idx_runs_video_created", "video_id", created_at.desc()),
    )

    video: Mapped[VideoModel] = relationship("VideoModel", back_populates="runs")
    camera_profile: Mapped[CameraProfileModel] = relationship("CameraProfileModel", back_populates="runs")
    job: Mapped[JobModel | None] = relationship(
        "JobModel", back_populates="run", uselist=False, cascade="all, delete-orphan"
    )
    events: Mapped[list[EventModel]] = relationship(
        "EventModel", back_populates="run", cascade="all, delete-orphan"
    )
    media_assets: Mapped[list[MediaAssetModel]] = relationship(
        "MediaAssetModel", back_populates="run", cascade="all, delete-orphan"
    )


class JobModel(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(
        Text, ForeignKey("runs.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    state: Mapped[str] = mapped_column(Text, nullable=False)
    stage: Mapped[str] = mapped_column(Text, nullable=False)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    leased_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    lease_expires_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    heartbeat_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    available_at: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        CheckConstraint("state IN ('QUEUED','RUNNING','SUCCEEDED','FAILED')", name="ck_job_state"),
        CheckConstraint(
            "stage IN ('QUEUED','NORMALIZING','DETECTING','VERIFYING','SCORING','WRITING_EVIDENCE','COMPLETE','FAILED')",
            name="ck_job_stage",
        ),
        CheckConstraint("progress BETWEEN 0 AND 100", name="ck_job_progress"),
        CheckConstraint("attempt >= 0", name="ck_job_attempt"),
        CheckConstraint("max_attempts BETWEEN 1 AND 5", name="ck_job_max_attempts"),
        Index("idx_jobs_claim", "state", "available_at", "created_at"),
    )

    run: Mapped[RunModel] = relationship("RunModel", back_populates="job")


class EventModel(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    run_id: Mapped[str] = mapped_column(
        Text, ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    start_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    end_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    primary_track_id: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_tier: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_quality: Mapped[float] = mapped_column(Float, nullable=False)
    verification_status: Mapped[str] = mapped_column(Text, nullable=False)
    facts_json: Mapped[str] = mapped_column(Text, nullable=False)
    decision_trace_json: Mapped[str] = mapped_column(Text, nullable=False)
    policy_sha256: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "event_type IN ('DROP','FORCEFUL_RELEASE','DRAGGING','VISIBLE_SUPPORT_OVERHANG','PROHIBITED_ZONE','STANDING_ON_PRODUCT')",
            name="ck_event_type",
        ),
        CheckConstraint("start_ms >= 0", name="ck_event_start_ms_ge0"),
        CheckConstraint("end_ms >= start_ms", name="ck_event_end_ms_ge_start"),
        CheckConstraint("risk_score BETWEEN 0 AND 100", name="ck_event_risk_score"),
        CheckConstraint("risk_tier IN ('LOW','MEDIUM','HIGH','CRITICAL')", name="ck_event_risk_tier"),
        CheckConstraint("evidence_quality BETWEEN 0 AND 1", name="ck_event_evidence_quality"),
        CheckConstraint(
            "verification_status IN ('NOT_RUN','PASSED','FAILED')", name="ck_event_verification_status"
        ),
        CheckConstraint("json_valid(facts_json)", name="ck_event_facts_json_valid"),
        CheckConstraint("json_valid(decision_trace_json)", name="ck_event_trace_json_valid"),
        CheckConstraint("length(policy_sha256) = 64", name="ck_event_policy_sha256_len"),
        UniqueConstraint("run_id", "event_type", "primary_track_id", "start_ms", name="uq_events_tuple"),
        Index("idx_events_run_time", "run_id", "start_ms"),
        Index("idx_events_type_tier", "event_type", "risk_tier"),
    )

    run: Mapped[RunModel] = relationship("RunModel", back_populates="events")
    reviews: Mapped[list[ReviewModel]] = relationship(
        "ReviewModel", back_populates="event", cascade="all, delete-orphan"
    )
    media_assets: Mapped[list[MediaAssetModel]] = relationship(
        "MediaAssetModel", back_populates="event", cascade="all, delete-orphan"
    )


class ReviewModel(Base):
    __tablename__ = "reviews"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    event_id: Mapped[str] = mapped_column(
        Text, ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    verdict: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")
    reviewer_name: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        CheckConstraint("revision > 0", name="ck_review_revision_gt0"),
        CheckConstraint("verdict IN ('CONFIRMED_RISK','REJECTED','UNCERTAIN')", name="ck_review_verdict"),
        CheckConstraint("length(note) <= 1000", name="ck_review_note_len"),
        CheckConstraint("length(reviewer_name) BETWEEN 1 AND 100", name="ck_review_reviewer_name_len"),
        UniqueConstraint("event_id", "revision", name="uq_reviews_event_revision"),
    )

    event: Mapped[EventModel] = relationship("EventModel", back_populates="reviews")


class MediaAssetModel(Base):
    __tablename__ = "media_assets"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    video_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("videos.id", ondelete="CASCADE"), nullable=True
    )
    run_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("runs.id", ondelete="CASCADE"), nullable=True
    )
    event_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("events.id", ondelete="CASCADE"), nullable=True
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    relative_path: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "kind IN ('SOURCE','NORMALIZED','ANNOTATED','TRACKS','EVENTS_JSON','MANIFEST','EVENT_CLIP','THUMBNAIL','TRACE')",
            name="ck_media_asset_kind",
        ),
        CheckConstraint("size_bytes >= 0", name="ck_media_asset_size_bytes_ge0"),
        CheckConstraint("length(sha256) = 64", name="ck_media_asset_sha256_len"),
        CheckConstraint(
            "video_id IS NOT NULL OR run_id IS NOT NULL OR event_id IS NOT NULL",
            name="ck_media_asset_owner_exists",
        ),
        Index(
            "idx_one_source_per_video",
            "video_id",
            unique=True,
            sqlite_where=text("kind = 'SOURCE'"),
        ),
    )

    video: Mapped[VideoModel | None] = relationship("VideoModel", back_populates="media_assets")
    run: Mapped[RunModel | None] = relationship("RunModel", back_populates="media_assets")
    event: Mapped[EventModel | None] = relationship("EventModel", back_populates="media_assets")


class WorkerLockModel(Base):
    __tablename__ = "worker_locks"

    lock_name: Mapped[str] = mapped_column(Text, primary_key=True)
    owner_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    model_sha256: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    heartbeat_at: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        CheckConstraint("lock_name = 'video-worker'", name="ck_worker_lock_name"),
        CheckConstraint(
            "status IN ('STARTING','READY','BUSY','ERROR','STOPPING')", name="ck_worker_lock_status"
        ),
    )
