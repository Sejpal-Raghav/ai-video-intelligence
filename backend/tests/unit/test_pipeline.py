from typing import Iterable, Sequence
import yaml
import pytest

from warehouse_ai.domain.enums import CameraMotion, EventType, ZoneKind, ZoneSeverity
from warehouse_ai.domain.models import (
    BehaviorRulesConfig,
    CameraProfile,
    Frame,
    RiskPolicyConfig,
    SupportRegionConfig,
    TrackedDetection,
    ZoneConfig,
)
from warehouse_ai.domain.risk import RiskEngine
from warehouse_ai.vision.pipeline import VisionPipeline


class SyntheticDetectorTracker:
    """Mock detector tracker providing synthetic drop sequence."""
    backend_name = "synthetic"
    model_sha256 = "synthetic"

    def __init__(self, sequence_generator) -> None:
        self.sequence_generator = sequence_generator

    def process(self, frames: Iterable[Frame]) -> Iterable[Sequence[TrackedDetection]]:
        for frame in frames:
            yield self.sequence_generator(frame.timestamp_ms)


@pytest.fixture
def behavior_config() -> BehaviorRulesConfig:
    with open("config/behavior_rules.v1.yaml", "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return BehaviorRulesConfig.model_validate(data)


@pytest.fixture
def risk_engine() -> RiskEngine:
    with open("config/risk_policy.v1.yaml", "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return RiskEngine(RiskPolicyConfig.model_validate(data))


@pytest.fixture
def demo_camera() -> CameraProfile:
    return CameraProfile(
        id="demo-camera",
        name="Demo fixed camera",
        camera_motion=CameraMotion.FIXED,
        frame_aspect_ratio=1.777778,
        floor_polygon=[(0.0, 0.5), (1.0, 0.5), (1.0, 1.0), (0.0, 1.0)],
        zones=[
            ZoneConfig(id="z-proh", kind=ZoneKind.PROHIBITED, severity=ZoneSeverity.CRITICAL, polygon=[(0.7, 0.5), (1.0, 0.5), (1.0, 1.0), (0.7, 1.0)]),
        ],
        support_regions=[],
        created_at="2026-09-04T00:00:00Z",
    )


def test_vision_pipeline_end_to_end(behavior_config, risk_engine, demo_camera):
    # Construct synthetic frames for drop scenario
    frames = [Frame(index=i, timestamp_ms=i * 100, bgr=None) for i in range(16)]

    def generate_detections(t_ms: int) -> list[TrackedDetection]:
        # Package track #1
        # 0-300: controlled with person #2
        # 400-600: released
        # 700-800: rapid drop motion downwards
        # 900: impact on floor
        # 1000-1500: settled
        dets: list[TrackedDetection] = []

        if t_ms <= 300:
            # Person #2 holding package #1
            dets.append(TrackedDetection(class_id="person", confidence=0.9, bbox_xyxy_norm=(0.25, 0.2, 0.45, 0.8), track_id=2))
            dets.append(TrackedDetection(class_id="package", confidence=0.85, bbox_xyxy_norm=(0.3, 0.3, 0.5, 0.5), track_id=1))
        elif t_ms <= 600:
            # Person steps away, package released
            dets.append(TrackedDetection(class_id="person", confidence=0.9, bbox_xyxy_norm=(0.85, 0.1, 0.98, 0.7), track_id=2))
            dets.append(TrackedDetection(class_id="package", confidence=0.85, bbox_xyxy_norm=(0.3, 0.32, 0.5, 0.52), track_id=1))
        elif t_ms == 700:
            dets.append(TrackedDetection(class_id="package", confidence=0.85, bbox_xyxy_norm=(0.3, 0.45, 0.5, 0.65), track_id=1))
        elif t_ms == 800:
            dets.append(TrackedDetection(class_id="package", confidence=0.85, bbox_xyxy_norm=(0.3, 0.60, 0.5, 0.80), track_id=1))
        else:
            # Impacted and settled on floor
            dets.append(TrackedDetection(class_id="package", confidence=0.85, bbox_xyxy_norm=(0.3, 0.70, 0.5, 0.90), track_id=1))

        return dets

    tracker = SyntheticDetectorTracker(generate_detections)
    pipeline = VisionPipeline(
        detector_tracker=tracker,
        config=behavior_config,
        risk_engine=risk_engine,
        camera_profile=demo_camera,
        verifier_enabled=False,
    )

    result = pipeline.run(frames)
    assert len(result.track_frames) == 16
    # Emitted drop event
    assert len(result.events) >= 1
    drop_ev = result.events[0]
    assert drop_ev.event_type == EventType.DROP
    assert drop_ev.risk_score >= 45
    assert drop_ev.primary_track_id == 1
