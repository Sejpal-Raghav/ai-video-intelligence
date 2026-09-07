"""Pydantic request and response schemas matching Blueprint Section 12, 14, and 15."""

from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class BaseContractModel(BaseModel):
    """Base schema strictly forbidding unknown extra fields."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class VideoResponse(BaseContractModel):
    id: str
    original_name: str
    sha256: str
    size_bytes: int
    duration_ms: int
    width: int
    height: int
    fps: float
    created_at: str
    expires_at: str


class ZoneSchema(BaseContractModel):
    id: str
    kind: Literal["ALLOWED", "PROHIBITED"]
    severity: Literal["NORMAL", "CRITICAL"]
    polygon: list[list[float]]


class SupportRegionSchema(BaseContractModel):
    id: str
    label: str
    polygon: list[list[float]]


class CameraProfileCreate(BaseContractModel):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,63}$")
    name: str = Field(min_length=1, max_length=100)
    frame_aspect_ratio: float = Field(gt=0)
    floor_polygon: list[list[float]]
    zones: list[ZoneSchema]
    support_regions: list[SupportRegionSchema]


class CameraProfileResponse(BaseContractModel):
    schema_version: str = "camera-profile.v1"
    id: str
    version: int
    name: str
    camera_motion: Literal["FIXED"] = "FIXED"
    frame_aspect_ratio: float
    floor_polygon: list[list[float]]
    zones: list[ZoneSchema]
    support_regions: list[SupportRegionSchema]
    created_at: str
    sha256: str


class RunCreate(BaseContractModel):
    video_id: str
    camera_profile_id: str
    camera_profile_version: int = Field(gt=0)
    mode: Literal["LIVE", "REPLAY"] = "LIVE"


class RunAccepted(BaseContractModel):
    run_id: str
    job_id: str
    status: Literal["QUEUED"] = "QUEUED"
    status_url: str


class JobStatusResponse(BaseContractModel):
    id: str
    run_id: str
    state: Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED"]
    stage: Literal[
        "QUEUED",
        "NORMALIZING",
        "DETECTING",
        "VERIFYING",
        "SCORING",
        "WRITING_EVIDENCE",
        "COMPLETE",
        "FAILED",
    ]
    progress: int = Field(ge=0, le=100)
    attempt: int = Field(ge=0)
    updated_at: str
    error: dict[str, Any] | None = None


class RiskDetail(BaseContractModel):
    score: int = Field(ge=0, le=100)
    tier: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    policy_version: str


class MediaLinks(BaseContractModel):
    clip_id: str | None = None
    thumbnail_id: str | None = None


class ReviewResponse(BaseContractModel):
    id: str
    event_id: str
    revision: int
    verdict: Literal["CONFIRMED_RISK", "REJECTED", "UNCERTAIN"]
    note: str
    reviewer_name: str
    created_at: str


class ReviewCreate(BaseContractModel):
    verdict: Literal["CONFIRMED_RISK", "REJECTED", "UNCERTAIN"]
    note: str = Field(default="", max_length=1000)
    reviewer_name: str = Field(min_length=1, max_length=100)


class EventDetail(BaseContractModel):
    id: str
    run_id: str
    event_type: Literal[
        "DROP",
        "FORCEFUL_RELEASE",
        "DRAGGING",
        "VISIBLE_SUPPORT_OVERHANG",
        "PROHIBITED_ZONE",
        "STANDING_ON_PRODUCT",
    ]
    start_ms: int
    end_ms: int
    primary_track_id: int
    risk: RiskDetail
    evidence_quality: float
    verification_status: Literal["NOT_RUN", "PASSED", "FAILED"]
    facts: dict[str, Any]
    explanation: str
    media: MediaLinks
    review: ReviewResponse | None = None


class EventPage(BaseContractModel):
    items: list[EventDetail]
    next_cursor: str | None = None


class RunDetail(BaseContractModel):
    id: str
    video_id: str
    camera_profile_id: str
    camera_profile_version: int
    mode: Literal["LIVE", "REPLAY"]
    status: Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED"]
    model_backend: str
    rules_version: str
    risk_policy_version: str
    warnings: list[str]
    manifest_url: str | None = None
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None


class CountItem(BaseContractModel):
    key: str
    count: int


class AnalyticsScope(BaseContractModel):
    run_ids: list[str]
    video_ids: list[str]


class AnalyticsSummary(BaseContractModel):
    scope: AnalyticsScope
    event_count: int
    reviewed_count: int
    by_event_type: list[CountItem]
    by_risk_tier: list[CountItem]
    by_review_verdict: list[CountItem]
    total_source_duration_ms: int
    false_alert_rate: float | None = None
