from dataclasses import dataclass, field
from typing import Any, Sequence
from pydantic import BaseModel, ConfigDict, Field, field_validator

from warehouse_ai.domain.enums import (
    CameraMotion,
    ObjectClass,
    ZoneKind,
    ZoneSeverity,
)


@dataclass(frozen=True)
class Frame:
    """Decoded frame at an authoritative PTS."""
    index: int
    timestamp_ms: int
    bgr: Any  # NDArray[uint8] - typed as Any in domain to avoid hard opencv/numpy coupling


@dataclass(frozen=True)
class Detection:
    """Single object detection."""
    class_id: str  # person|package|pallet|equipment
    confidence: float  # inclusive [0.0, 1.0]
    bbox_xyxy_norm: tuple[float, float, float, float]

    def __post_init__(self) -> None:
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(f"Confidence {self.confidence} must be in [0.0, 1.0]")
        x1, y1, x2, y2 = self.bbox_xyxy_norm
        if not (0.0 <= x1 <= 1.0 and 0.0 <= y1 <= 1.0 and 0.0 <= x2 <= 1.0 and 0.0 <= y2 <= 1.0):
            raise ValueError(f"Bounding box {self.bbox_xyxy_norm} must be clamped to [0.0, 1.0]")
        if x1 >= x2 or y1 >= y2:
            raise ValueError(f"Invalid bounding box dimensions: x1 ({x1}) < x2 ({x2}) and y1 ({y1}) < y2 ({y2}) required")


@dataclass(frozen=True)
class TrackedDetection(Detection):
    """Detection associated with a tracker ID."""
    track_id: int
    is_interpolated: bool = False


@dataclass(frozen=True)
class PersonPose:
    """Pose keypoints for a tracked person."""
    person_track_id: int
    # COCO keypoint index -> (normalized x, normalized y, confidence)
    keypoints: dict[int, tuple[float, float, float]] = field(default_factory=dict)


class TrackObservation(BaseModel):
    """Serialized observation for a track within a frame."""
    model_config = ConfigDict(extra="forbid")

    track_id: int
    class_id: str
    confidence: float = Field(ge=0.0, le=1.0)
    bbox_xyxy_norm: tuple[float, float, float, float]
    is_interpolated: bool = False

    @field_validator("bbox_xyxy_norm")
    @classmethod
    def validate_bbox(cls, v: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
        x1, y1, x2, y2 = v
        if not (0.0 <= x1 <= 1.0 and 0.0 <= y1 <= 1.0 and 0.0 <= x2 <= 1.0 and 0.0 <= y2 <= 1.0):
            raise ValueError("Coordinates must be in [0, 1]")
        if x1 >= x2 or y1 >= y2:
            raise ValueError("Coordinates must satisfy x1 < x2 and y1 < y2")
        return (round(x1, 6), round(y1, 6), round(x2, 6), round(y2, 6))

    @field_validator("confidence")
    @classmethod
    def round_confidence(cls, v: float) -> float:
        return round(v, 6)


class TrackFrame(BaseModel):
    """Single inference frame holding all tracked detections (Section 9)."""
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "track-frame.v1"
    frame_index: int
    timestamp_ms: int
    frame_width: int
    frame_height: int
    tracks: list[TrackObservation]


class ZoneConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: ZoneKind
    severity: ZoneSeverity
    polygon: list[tuple[float, float]]


class SupportRegionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    polygon: list[tuple[float, float]]


class CameraProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "camera-profile.v1"
    id: str
    name: str
    camera_motion: CameraMotion = CameraMotion.FIXED
    frame_aspect_ratio: float
    floor_polygon: list[tuple[float, float]]
    zones: list[ZoneConfig] = Field(default_factory=list)
    support_regions: list[SupportRegionConfig] = Field(default_factory=list)
    created_at: str
    profile_sha256: str = ""


# Configurations parsed from YAML files
class CommonRulesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    minimum_non_interpolated_observations: int
    minimum_median_detection_confidence: float
    minimum_track_coverage: float
    maximum_interpolation_fraction: float
    maximum_boundary_fraction: float
    boundary_margin_norm: float
    maximum_interpolation_gap_ms: int


class RelationshipRulesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    near_package_diagonals: float
    co_moving_minimum_speed_hps: float
    co_moving_minimum_cosine: float
    co_moving_minimum_ms: int
    equipment_horizontal_overlap_ratio: float
    equipment_top_tolerance_package_h: float
    equipment_bottom_tolerance_package_h: float
    floor_person_bottom_tolerance_person_h: float
    visible_footprint_bottom_fraction: float


class DropForcefulReleaseRulesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    controlled_minimum_ms: int
    release_minimum_ms: int
    motion_window_ms: int
    drop_minimum_displacement_h: float
    drop_minimum_peak_down_speed_hps: float
    forceful_minimum_horizontal_displacement_w: float
    forceful_minimum_peak_horizontal_speed_hps: float
    impact_maximum_ms_after_motion: int
    impact_minimum_pre_speed_hps: float
    impact_maximum_post_speed_hps: float
    impact_deceleration_window_ms: int
    settle_maximum_speed_hps: float
    settle_minimum_ms: int
    settle_timeout_ms: int
    cooldown_ms: int


class DraggingRulesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    qualification_window_ms: int
    minimum_horizontal_displacement_w: float
    maximum_vertical_displacement_h: float
    minimum_direction_agreement: float
    direction_increment_deadband_w: float
    minimum_direction_increments: int
    active_minimum_horizontal_speed_hps: float
    end_inactivity_ms: int
    merge_gap_ms: int


class PlacementRulesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stationary_maximum_speed_hps: float
    prohibited_zone_dwell_ms: int
    prohibited_zone_exit_ms: int
    minimum_visible_support_ratio: float
    visible_support_dwell_ms: int
    visible_support_exit_ms: int


class StandingOnProductRulesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    minimum_ankle_confidence: float
    package_box_expansion_fraction: float
    package_maximum_speed_hps: float
    dwell_ms: int
    end_hysteresis_ms: int
    merge_gap_ms: int


class BehaviorRulesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "behavior-rules.v1"
    common: CommonRulesConfig
    relationships: RelationshipRulesConfig
    drop_forceful_release: DropForcefulReleaseRulesConfig
    dragging: DraggingRulesConfig
    placement: PlacementRulesConfig
    standing_on_product: StandingOnProductRulesConfig


class RiskPolicyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "risk-policy.v1"
    bases: dict[str, int]
    tiers: dict[str, tuple[int, int]]
    zone_bonus: dict[str, int]
