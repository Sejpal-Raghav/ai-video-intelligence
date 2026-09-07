from dataclasses import dataclass, field
from typing import Any, Sequence

from warehouse_ai.domain.enums import EventType
from warehouse_ai.domain.models import (
    BehaviorRulesConfig,
    CameraProfile,
    Frame,
    TrackFrame,
    TrackObservation,
)
from warehouse_ai.domain.risk import RiskEngine
from warehouse_ai.vision.adapters.base import DetectorTracker
from warehouse_ai.vision.features import (
    KinematicObservation,
    eval_near,
    eval_on_floor,
    eval_supported_by,
    extract_track_kinematics,
)
from warehouse_ai.vision.rules.dragging import DraggingEngine, EmittedDraggingEvent
from warehouse_ai.vision.rules.drop_forceful_release import EmittedHeroEvent, HeroStateMachine
from warehouse_ai.vision.rules.placement import EmittedPlacementEvent, PlacementEngine
from warehouse_ai.vision.tracking import interpolate_tracks


@dataclass
class EmittedEvent:
    event_type: EventType
    start_ms: int
    end_ms: int
    keyframe_ms: int
    primary_track_id: int
    associated_track_ids: list[int]
    risk_score: int
    risk_tier: str
    evidence_quality: float
    verification_status: str
    facts_json: dict[str, Any]
    decision_trace_json: dict[str, Any]


@dataclass
class VisionPipelineResult:
    events: list[EmittedEvent] = field(default_factory=list)
    review_candidates: list[EmittedEvent] = field(default_factory=list)
    track_frames: list[TrackFrame] = field(default_factory=list)


class VisionPipeline:
    """Orchestrates video frame processing, tracking, kinematic extraction, and behavior engines (Section 4.3 & 18)."""

    def __init__(
        self,
        detector_tracker: DetectorTracker,
        config: BehaviorRulesConfig,
        risk_engine: RiskEngine,
        camera_profile: CameraProfile,
        verifier_enabled: bool = False,
    ) -> None:
        self.detector_tracker = detector_tracker
        self.config = config
        self.risk_engine = risk_engine
        self.camera_profile = camera_profile
        self.verifier_enabled = verifier_enabled

    def run(
        self,
        frames: Sequence[Frame],
        expected_total_frames: int | None = None,
    ) -> VisionPipelineResult:
        if not frames:
            return VisionPipelineResult()

        frames_list = list(frames)
        total_frames = expected_total_frames or len(frames_list)

        # 1. Run detection and tracking across all frames
        detection_sequences = list(self.detector_tracker.process(frames_list))

        # 2. Build initial TrackFrame objects
        raw_track_frames: list[TrackFrame] = []
        for frame, detections in zip(frames_list, detection_sequences, strict=False):
            tracks = [
                TrackObservation(
                    track_id=d.track_id,
                    class_id=d.class_id,
                    confidence=d.confidence,
                    bbox_xyxy_norm=d.bbox_xyxy_norm,
                    is_interpolated=d.is_interpolated,
                )
                for d in detections
            ]
            raw_track_frames.append(
                TrackFrame(
                    schema_version="track-frame.v1",
                    frame_index=frame.index,
                    timestamp_ms=frame.timestamp_ms,
                    frame_width=1920,
                    frame_height=1080,
                    tracks=tracks,
                )
            )

        # 3. Gap interpolation (<= 200 ms)
        track_frames = interpolate_tracks(
            raw_track_frames,
            max_gap_ms=self.config.common.maximum_interpolation_gap_ms,
        )

        # 4. Group observations by track_id
        observations_by_track: dict[int, list[TrackObservation]] = {}
        timestamps_by_track: dict[int, list[int]] = {}
        track_classes: dict[int, str] = {}

        for tf in track_frames:
            for obs in tf.tracks:
                observations_by_track.setdefault(obs.track_id, []).append(obs)
                timestamps_by_track.setdefault(obs.track_id, []).append(tf.timestamp_ms)
                track_classes[obs.track_id] = obs.class_id

        # 5. Extract kinematics for all tracks
        kinematics_by_track: dict[int, dict[int, KinematicObservation]] = {}
        for tr_id, obs_list in observations_by_track.items():
            ts_list = timestamps_by_track[tr_id]
            kin_list = extract_track_kinematics(obs_list, ts_list)
            kinematics_by_track[tr_id] = {kin.timestamp_ms: kin for kin in kin_list}

        # 6. Instantiate behavior engines for package tracks
        package_track_ids = [
            tr_id for tr_id, cls in track_classes.items() if cls == "package"
        ]
        person_track_ids = [
            tr_id for tr_id, cls in track_classes.items() if cls == "person"
        ]
        equipment_track_ids = [
            tr_id for tr_id, cls in track_classes.items() if cls == "equipment"
        ]

        hero_engines = {
            pkg_id: HeroStateMachine(pkg_id, self.config, self.risk_engine)
            for pkg_id in package_track_ids
        }
        dragging_engines = {
            pkg_id: DraggingEngine(pkg_id, self.config, self.risk_engine)
            for pkg_id in package_track_ids
        }
        placement_engines = {
            pkg_id: PlacementEngine(pkg_id, self.config, self.camera_profile, self.risk_engine)
            for pkg_id in package_track_ids
        }

        all_emitted_events: list[EmittedHeroEvent | EmittedDraggingEvent | EmittedPlacementEvent] = []

        # 7. Step through frames chronologically
        for tf in track_frames:
            t = tf.timestamp_ms
            obs_map = {obs.track_id: obs for obs in tf.tracks}

            for pkg_id in package_track_ids:
                if pkg_id not in obs_map or pkg_id not in kinematics_by_track:
                    continue

                pkg_obs = obs_map[pkg_id]
                pkg_kin = kinematics_by_track[pkg_id].get(t)
                if not pkg_kin:
                    continue

                # Relationship checks against persons and equipment
                is_handled = False
                is_supported = False
                is_on_floor = False
                qualifying_dragging_persons: list[int] = []

                # Equipment support check
                for eq_id in equipment_track_ids:
                    if eq_id in obs_map:
                        eq_obs = obs_map[eq_id]
                        sup_eval = eval_supported_by(
                            pkg_box=pkg_obs.bbox_xyxy_norm,
                            equip_box=eq_obs.bbox_xyxy_norm,
                            min_overlap_ratio=self.config.relationships.equipment_horizontal_overlap_ratio,
                            top_tol_h=self.config.relationships.equipment_top_tolerance_package_h,
                            bottom_tol_h=self.config.relationships.equipment_bottom_tolerance_package_h,
                            pkg_id=pkg_id,
                            equip_id=eq_id,
                        )
                        if sup_eval.passed:
                            is_supported = True
                            break

                # Person proximity and floor check
                for p_id in person_track_ids:
                    if p_id in obs_map:
                        p_obs = obs_map[p_id]
                        near_eval = eval_near(
                            person_box=p_obs.bbox_xyxy_norm,
                            pkg_box=pkg_obs.bbox_xyxy_norm,
                            threshold_diag_mult=self.config.relationships.near_package_diagonals,
                            person_id=p_id,
                            pkg_id=pkg_id,
                        )
                        floor_eval = eval_on_floor(
                            pkg_box=pkg_obs.bbox_xyxy_norm,
                            person_box=p_obs.bbox_xyxy_norm,
                            floor_polygon=self.camera_profile.floor_polygon,
                            bottom_tol_person_h=self.config.relationships.floor_person_bottom_tolerance_person_h,
                            pkg_id=pkg_id,
                            person_id=p_id,
                        )
                        if floor_eval.passed:
                            is_on_floor = True

                        # Dragging qualification check
                        if floor_eval.passed and near_eval.passed and not is_supported:
                            qualifying_dragging_persons.append(p_id)

                        if near_eval.passed:
                            is_handled = True

                all_pkg_obs = observations_by_track[pkg_id]

                # Update Hero State Machine
                hero_ev = hero_engines[pkg_id].update(
                    kin=pkg_kin,
                    raw_obs=pkg_obs,
                    is_handled_or_supported=(is_handled or is_supported),
                    is_on_floor_or_supported=(is_on_floor or is_supported),
                    all_track_observations=all_pkg_obs,
                    expected_frames_window=total_frames,
                )
                if hero_ev is not None:
                    all_emitted_events.append(hero_ev)

                # Update Dragging Engine
                drag_ev = dragging_engines[pkg_id].update(
                    kin=pkg_kin,
                    raw_obs=pkg_obs,
                    qualifying_person_ids=qualifying_dragging_persons,
                    all_track_obs=all_pkg_obs,
                    expected_frames=total_frames,
                )
                if drag_ev is not None:
                    all_emitted_events.append(drag_ev)

                # Update Placement Engine
                place_evs = placement_engines[pkg_id].update(
                    kin=pkg_kin,
                    raw_obs=pkg_obs,
                    all_track_obs=all_pkg_obs,
                    expected_frames=total_frames,
                )
                all_emitted_events.extend(place_evs)

        # 8. Flush dragging intervals at end
        for pkg_id, drag_eng in dragging_engines.items():
            flushed = drag_eng.flush(observations_by_track[pkg_id], expected_frames=total_frames)
            if flushed is not None:
                all_emitted_events.append(flushed)

        # 9. Format output events and review candidates
        publishable_events: list[EmittedEvent] = []
        review_candidates: list[EmittedEvent] = []

        for ev in all_emitted_events:
            assoc_ids = getattr(ev, "associated_track_ids", [])
            emitted = EmittedEvent(
                event_type=ev.event_type,
                start_ms=ev.start_ms,
                end_ms=ev.end_ms,
                keyframe_ms=ev.keyframe_ms,
                primary_track_id=ev.primary_track_id,
                associated_track_ids=assoc_ids,
                risk_score=ev.risk_score,
                risk_tier=ev.risk_tier.value,
                evidence_quality=ev.evidence_quality,
                verification_status="NOT_RUN",
                facts_json=ev.measured_facts,
                decision_trace_json=ev.decision_trace.model_dump(),
            )

            if ev.is_review_candidate:
                review_candidates.append(emitted)
            else:
                publishable_events.append(emitted)

        return VisionPipelineResult(
            events=publishable_events,
            review_candidates=review_candidates,
            track_frames=track_frames,
        )
