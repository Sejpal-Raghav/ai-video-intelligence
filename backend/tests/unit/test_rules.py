import yaml
import pytest

from warehouse_ai.domain.enums import CameraMotion, EventType, ZoneKind, ZoneSeverity
from warehouse_ai.domain.models import (
    BehaviorRulesConfig,
    CameraProfile,
    RiskPolicyConfig,
    SupportRegionConfig,
    TrackObservation,
    ZoneConfig,
)
from warehouse_ai.vision.features import KinematicObservation
from warehouse_ai.domain.risk import RiskEngine
from warehouse_ai.vision.rules.base import evaluate_event_quality_gate
from warehouse_ai.vision.rules.dragging import DraggingEngine
from warehouse_ai.vision.rules.drop_forceful_release import HeroStateMachine, HeroState
from warehouse_ai.vision.rules.placement import PlacementEngine


@pytest.fixture
def behavior_config() -> BehaviorRulesConfig:
    with open("config/behavior_rules.v1.yaml", "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return BehaviorRulesConfig.model_validate(data)


@pytest.fixture
def risk_policy() -> RiskPolicyConfig:
    with open("config/risk_policy.v1.yaml", "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return RiskPolicyConfig.model_validate(data)


@pytest.fixture
def risk_engine(risk_policy) -> RiskEngine:
    return RiskEngine(risk_policy)


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
        support_regions=[
            SupportRegionConfig(id="pallet-1", label="Pallet 1", polygon=[(0.1, 0.5), (0.4, 0.5), (0.4, 0.8), (0.1, 0.8)])
        ],
        created_at="2026-09-04T00:00:00Z",
    )


def test_quality_gate_evaluation(behavior_config):
    # 6 observations, confidence 0.8, no boundary touching
    obs = [
        TrackObservation(track_id=1, class_id="package", confidence=0.8, bbox_xyxy_norm=(0.2, 0.2, 0.4, 0.4))
        for _ in range(6)
    ]
    res = evaluate_event_quality_gate(obs, expected_inference_frames=6, config=behavior_config.common)
    assert res.passed is True
    assert res.track_coverage == 1.0
    assert res.evidence_quality >= 0.70


def test_hero_state_machine_drop_sequence(behavior_config, risk_engine):
    sm = HeroStateMachine(package_track_id=1, config=behavior_config, risk_engine=risk_engine)

    # 1. Controlled phase (>= 300 ms)
    all_obs = []
    for t in [0, 100, 200, 300]:
        raw = TrackObservation(track_id=1, class_id="package", confidence=0.8, bbox_xyxy_norm=(0.3, 0.2, 0.5, 0.4))
        all_obs.append(raw)
        kin = KinematicObservation(1, t, 0.4, 0.3, 0.2, 0.2, 0.0, 0.0, 0.0, False, 0.8, raw.bbox_xyxy_norm)
        sm.update(kin, raw, is_handled_or_supported=True, is_on_floor_or_supported=False, all_track_observations=all_obs)

    assert sm.state == HeroState.CONTROLLED

    # 2. Release phase (neither handled nor supported >= 200 ms)
    for t in [400, 500, 600]:
        raw = TrackObservation(track_id=1, class_id="package", confidence=0.8, bbox_xyxy_norm=(0.3, 0.2, 0.5, 0.4))
        all_obs.append(raw)
        kin = KinematicObservation(1, t, 0.4, 0.3, 0.2, 0.2, 0.0, 0.0, 0.0, False, 0.8, raw.bbox_xyxy_norm)
        sm.update(kin, raw, is_handled_or_supported=False, is_on_floor_or_supported=False, all_track_observations=all_obs)

    assert sm.state == HeroState.RELEASED

    # 3. Rapid motion phase: package drops vertically
    # cy moves from 0.3 to 0.55 (disp = 0.25 / 0.2 = 1.25 h_ref >= 0.50 h_ref), vy_hps = 1.5 h/s
    for t in [700, 800]:
        raw = TrackObservation(track_id=1, class_id="package", confidence=0.8, bbox_xyxy_norm=(0.3, 0.45, 0.5, 0.65))
        all_obs.append(raw)
        kin = KinematicObservation(1, t, 0.4, 0.55, 0.2, 0.2, 0.0, 1.5, 1.5, False, 0.8, raw.bbox_xyxy_norm)
        sm.update(kin, raw, is_handled_or_supported=False, is_on_floor_or_supported=False, all_track_observations=all_obs)

    assert sm.state == HeroState.RAPID_MOTION

    # 4. Impact phase: speed falls from 1.5 to 0.2 within 300 ms
    t = 900
    raw = TrackObservation(track_id=1, class_id="package", confidence=0.8, bbox_xyxy_norm=(0.3, 0.55, 0.5, 0.75))
    all_obs.append(raw)
    kin = KinematicObservation(1, t, 0.4, 0.65, 0.2, 0.2, 0.0, 0.2, 0.2, False, 0.8, raw.bbox_xyxy_norm)
    sm.update(kin, raw, is_handled_or_supported=False, is_on_floor_or_supported=True, all_track_observations=all_obs)
    assert sm.state == HeroState.IMPACT_CANDIDATE

    # 5. Settle phase: speed <= 0.25 h/s for >= 400 ms -> EMIT
    event = None
    for t in [1000, 1100, 1200, 1300, 1400]:
        raw = TrackObservation(track_id=1, class_id="package", confidence=0.8, bbox_xyxy_norm=(0.3, 0.55, 0.5, 0.75))
        all_obs.append(raw)
        kin = KinematicObservation(1, t, 0.4, 0.65, 0.2, 0.2, 0.0, 0.05, 0.05, False, 0.8, raw.bbox_xyxy_norm)
        res = sm.update(kin, raw, is_handled_or_supported=False, is_on_floor_or_supported=True, all_track_observations=all_obs, expected_frames_window=len(all_obs))
        if res:
            event = res
            break

    assert event is not None
    assert event.event_type == EventType.DROP
    assert event.risk_score >= 45
    assert sm.state == HeroState.OBSERVING


def test_placement_prohibited_zone(behavior_config, demo_camera, risk_engine):
    pe = PlacementEngine(package_track_id=1, config=behavior_config, camera_profile=demo_camera, risk_engine=risk_engine)

    # Stationary package in prohibited zone (x in [0.7, 1.0], y in [0.5, 1.0])
    all_obs = []
    events = []
    # Dwell for 1100 ms (exceeds 1000 ms requirement)
    for t in range(0, 1200, 100):
        raw = TrackObservation(track_id=1, class_id="package", confidence=0.85, bbox_xyxy_norm=(0.75, 0.6, 0.9, 0.8))
        all_obs.append(raw)
        kin = KinematicObservation(1, t, 0.825, 0.7, 0.15, 0.2, 0.0, 0.0, 0.0, False, 0.85, raw.bbox_xyxy_norm)
        evs = pe.update(kin, raw, all_obs, expected_frames=len(all_obs))
        events.extend(evs)

    assert len(events) == 1
    assert events[0].event_type == EventType.PROHIBITED_ZONE
    assert events[0].risk_tier.value in ("HIGH", "CRITICAL")
