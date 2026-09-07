from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Sequence

from warehouse_ai.domain.decision_trace import DecisionTrace, PredicateEvaluation, StateTransition
from warehouse_ai.domain.enums import EventType, RiskTier
from warehouse_ai.domain.models import BehaviorRulesConfig, DropForcefulReleaseRulesConfig, TrackObservation
from warehouse_ai.domain.risk import RiskEngine
from warehouse_ai.vision.features import KinematicObservation, compute_reference_dimensions
from warehouse_ai.vision.rules.base import evaluate_event_quality_gate


class HeroState(str, Enum):
    OBSERVING = "OBSERVING"
    CONTROLLED = "CONTROLLED"
    RELEASED = "RELEASED"
    RAPID_MOTION = "RAPID_MOTION"
    IMPACT_CANDIDATE = "IMPACT_CANDIDATE"
    EMIT = "EMIT"


@dataclass
class EmittedHeroEvent:
    event_type: EventType
    start_ms: int
    end_ms: int
    keyframe_ms: int
    primary_track_id: int
    risk_score: int
    risk_tier: RiskTier
    evidence_quality: float
    is_review_candidate: bool
    measured_facts: dict[str, Any]
    decision_trace: DecisionTrace


class HeroStateMachine:
    """Deterministic state machine for DROP_OR_FORCEFUL_RELEASE (Section 10.2)."""

    def __init__(
        self,
        package_track_id: int,
        config: BehaviorRulesConfig,
        risk_engine: RiskEngine,
    ) -> None:
        self.track_id = package_track_id
        self.config = config
        self.rule_cfg: DropForcefulReleaseRulesConfig = config.drop_forceful_release
        self.risk_engine = risk_engine

        self.state = HeroState.OBSERVING
        self.transitions: list[StateTransition] = []

        # State tracking timestamps and kinematics
        self.controlled_start_ms: int | None = None
        self.released_ms: int | None = None
        self.release_cx: float = 0.0
        self.release_cy: float = 0.0
        self.rapid_motion_ms: int | None = None
        self.impact_candidate_ms: int | None = None
        self.settle_start_ms: int | None = None
        self.last_emit_ms: int = -99999

        # Peak measurements during motion
        self.peak_speed_hps: float = 0.0
        self.peak_down_speed_hps: float = 0.0
        self.peak_horiz_speed_hps: float = 0.0
        self.max_down_disp_h: float = 0.0
        self.max_horiz_disp_w: float = 0.0
        self.keyframe_ms: int = 0

        # Pre-contact speed history for impact detection (window of 300ms)
        self.recent_speeds: list[tuple[int, float]] = []

    def _record_transition(
        self, to_state: HeroState, timestamp_ms: int, reason: str, preds: list[PredicateEvaluation] | None = None
    ) -> None:
        trans = StateTransition(
            from_state=self.state.value,
            to_state=to_state.value,
            timestamp_ms=timestamp_ms,
            reason=reason,
            predicates=preds or [],
        )
        self.transitions.append(trans)
        self.state = to_state

    def update(
        self,
        kin: KinematicObservation,
        raw_obs: TrackObservation,
        is_handled_or_supported: bool,
        is_on_floor_or_supported: bool,
        all_track_observations: Sequence[TrackObservation],
        expected_frames_window: int = 10,
    ) -> EmittedHeroEvent | None:
        t = kin.timestamp_ms

        # Cooldown check
        if (t - self.last_emit_ms) < self.rule_cfg.cooldown_ms:
            return None

        # Update running kinematics
        w_ref, h_ref = compute_reference_dimensions([raw_obs])
        self.recent_speeds.append((t, kin.speed_hps))
        self.recent_speeds = [(ts, sp) for ts, sp in self.recent_speeds if (t - ts) <= 350]

        # State Machine Transitions (Section 10.2)
        if self.state == HeroState.OBSERVING:
            if is_handled_or_supported:
                if self.controlled_start_ms is None:
                    self.controlled_start_ms = t
                elif (t - self.controlled_start_ms) >= self.rule_cfg.controlled_minimum_ms:
                    self._record_transition(HeroState.CONTROLLED, t, "Handled or supported continuously >= 300ms")
            else:
                self.controlled_start_ms = None

        elif self.state == HeroState.CONTROLLED:
            if not is_handled_or_supported:
                if self.released_ms is None:
                    self.released_ms = t
                elif (t - self.released_ms) >= self.rule_cfg.release_minimum_ms:
                    self.release_cx = kin.cx_smooth
                    self.release_cy = kin.cy_smooth
                    self.peak_speed_hps = kin.speed_hps
                    self.peak_down_speed_hps = kin.vy_hps
                    self.peak_horiz_speed_hps = abs(kin.vx_hps)
                    self.max_down_disp_h = 0.0
                    self.max_horiz_disp_w = 0.0
                    self.keyframe_ms = t
                    self._record_transition(HeroState.RELEASED, t, "Neither handled nor supported >= 200ms")
            else:
                self.released_ms = None

        elif self.state == HeroState.RELEASED:
            elapsed_release = t - (self.released_ms or t)
            # Update peak motion
            down_disp_h = (kin.cy_smooth - self.release_cy) / h_ref
            horiz_disp_w = abs(kin.cx_smooth - self.release_cx) / w_ref
            self.max_down_disp_h = max(self.max_down_disp_h, down_disp_h)
            self.max_horiz_disp_w = max(self.max_horiz_disp_w, horiz_disp_w)

            if kin.vy_hps > self.peak_down_speed_hps:
                self.peak_down_speed_hps = kin.vy_hps
                self.keyframe_ms = t
            if abs(kin.vx_hps) > self.peak_horiz_speed_hps:
                self.peak_horiz_speed_hps = abs(kin.vx_hps)
                self.keyframe_ms = t
            if kin.speed_hps > self.peak_speed_hps:
                self.peak_speed_hps = kin.speed_hps

            # Motion checks within motion_window_ms (700 ms)
            drop_motion = (
                self.max_down_disp_h >= self.rule_cfg.drop_minimum_displacement_h
                and self.peak_down_speed_hps >= self.rule_cfg.drop_minimum_peak_down_speed_hps
            )
            lateral_motion = (
                self.max_horiz_disp_w >= self.rule_cfg.forceful_minimum_horizontal_displacement_w
                and self.peak_horiz_speed_hps >= self.rule_cfg.forceful_minimum_peak_horizontal_speed_hps
            )

            if drop_motion or lateral_motion:
                self.rapid_motion_ms = t
                reason = "Drop motion threshold reached" if drop_motion else "Forceful lateral motion threshold reached"
                self._record_transition(HeroState.RAPID_MOTION, t, reason)
            elif elapsed_release > self.rule_cfg.motion_window_ms:
                self._record_transition(HeroState.OBSERVING, t, "Motion threshold not met within 700ms")
                self._reset_tracking()

        elif self.state == HeroState.RAPID_MOTION:
            elapsed_rapid = t - (self.rapid_motion_ms or t)
            # Update kinematics
            down_disp_h = (kin.cy_smooth - self.release_cy) / h_ref
            horiz_disp_w = abs(kin.cx_smooth - self.release_cx) / w_ref
            self.max_down_disp_h = max(self.max_down_disp_h, down_disp_h)
            self.max_horiz_disp_w = max(self.max_horiz_disp_w, horiz_disp_w)
            if kin.speed_hps > self.peak_speed_hps:
                self.peak_speed_hps = kin.speed_hps
                self.keyframe_ms = t

            # Impact check within 1200 ms:
            # 1) Total speed falls from >= 1.25 to <= 0.35 within 300 ms
            # 2) ON_FLOOR or SUPPORTED_BY becomes True while pre-contact total speed was >= 1.25
            max_recent_pre = max([sp for ts, sp in self.recent_speeds if (t - ts) <= self.rule_cfg.impact_deceleration_window_ms], default=0.0)
            decel_impact = (max_recent_pre >= self.rule_cfg.impact_minimum_pre_speed_hps and kin.speed_hps <= self.rule_cfg.impact_maximum_post_speed_hps)
            contact_impact = (is_on_floor_or_supported and max_recent_pre >= self.rule_cfg.impact_minimum_pre_speed_hps)

            if decel_impact or contact_impact:
                self.impact_candidate_ms = t
                reason = "Impact detected via deceleration" if decel_impact else "Impact detected via floor/support contact"
                self._record_transition(HeroState.IMPACT_CANDIDATE, t, reason)
            elif elapsed_rapid > self.rule_cfg.impact_maximum_ms_after_motion:
                self._record_transition(HeroState.OBSERVING, t, "No impact within 1200ms of rapid motion")
                self._reset_tracking()

        elif self.state == HeroState.IMPACT_CANDIDATE:
            elapsed_impact = t - (self.impact_candidate_ms or t)
            if kin.speed_hps <= self.rule_cfg.settle_maximum_speed_hps:
                if self.settle_start_ms is None:
                    self.settle_start_ms = t
                elif (t - self.settle_start_ms) >= self.rule_cfg.settle_minimum_ms:
                    # EMIT!
                    self._record_transition(HeroState.EMIT, t, "Package settled <= 0.25 h/s for >= 400ms")
                    event = self._build_event(t, all_track_observations, expected_frames_window)
                    self.last_emit_ms = t
                    self._record_transition(HeroState.OBSERVING, t, "Reset to observing after emit")
                    self._reset_tracking()
                    return event
            else:
                self.settle_start_ms = None

            if elapsed_impact > self.rule_cfg.settle_timeout_ms:
                # Settle timeout: write REVIEW_CANDIDATE artifact
                event = self._build_event(t, all_track_observations, expected_frames_window, force_review_candidate=True)
                self._record_transition(HeroState.OBSERVING, t, "Settle timeout exceeded 1000ms -> REVIEW_CANDIDATE")
                self._reset_tracking()
                return event

        return None

    def _reset_tracking(self) -> None:
        self.controlled_start_ms = None
        self.released_ms = None
        self.rapid_motion_ms = None
        self.impact_candidate_ms = None
        self.settle_start_ms = None
        self.peak_speed_hps = 0.0
        self.peak_down_speed_hps = 0.0
        self.peak_horiz_speed_hps = 0.0
        self.max_down_disp_h = 0.0
        self.max_horiz_disp_w = 0.0

    def _build_event(
        self,
        settled_t: int,
        all_track_obs: Sequence[TrackObservation],
        expected_frames: int,
        force_review_candidate: bool = False,
    ) -> EmittedHeroEvent:
        start_ms = self.released_ms or (settled_t - 1000)
        end_ms = settled_t
        keyframe_ms = self.keyframe_ms or (start_ms + (end_ms - start_ms) // 2)

        # Classify as FORCEFUL_RELEASE when horizontal displacement >= vertical displacement in reference units
        if self.max_horiz_disp_w >= self.max_down_disp_h:
            event_type = EventType.FORCEFUL_RELEASE
        else:
            event_type = EventType.DROP

        # Evaluate quality gate
        q_res = evaluate_event_quality_gate(all_track_obs, expected_frames, self.config.common)
        is_review_candidate = force_review_candidate or (not q_res.passed)

        # Kinematic metadata
        measured_facts = {
            "peak_speed_hps": round(self.peak_speed_hps, 3),
            "peak_down_speed_hps": round(self.peak_down_speed_hps, 3),
            "peak_horiz_speed_hps": round(self.peak_horiz_speed_hps, 3),
            "vertical_displacement_h": round(self.max_down_disp_h, 3),
            "horizontal_displacement_w": round(self.max_horiz_disp_w, 3),
            "released_ms": self.released_ms,
            "rapid_motion_ms": self.rapid_motion_ms,
            "impact_ms": self.impact_candidate_ms,
            "settled_ms": settled_t,
        }

        # Calculate risk score
        risk_res = self.risk_engine.calculate(
            event_type=event_type,
            peak_speed_hps=self.peak_speed_hps,
            duration_seconds=(end_ms - start_ms) / 1000.0,
            metadata=measured_facts,
        )

        trace = DecisionTrace(
            event_type=event_type.value,
            primary_track_id=self.track_id,
            associated_track_ids=[],
            start_ms=start_ms,
            end_ms=end_ms,
            keyframe_ms=keyframe_ms,
            track_coverage=q_res.track_coverage,
            interpolation_fraction=q_res.interpolation_fraction,
            median_detection_confidence=q_res.median_confidence,
            track_quality=q_res.track_quality,
            evidence_quality=q_res.evidence_quality,
            measured_facts=measured_facts,
            state_transitions=list(self.transitions),
            evaluations=q_res.evaluations,
            risk_score=risk_res.score,
            risk_tier=risk_res.tier.value,
            explanation=risk_res.explanation,
            formula_breakdown=risk_res.formula_breakdown,
        )

        return EmittedHeroEvent(
            event_type=event_type,
            start_ms=start_ms,
            end_ms=end_ms,
            keyframe_ms=keyframe_ms,
            primary_track_id=self.track_id,
            risk_score=risk_res.score,
            risk_tier=risk_res.tier,
            evidence_quality=q_res.evidence_quality,
            is_review_candidate=is_review_candidate,
            measured_facts=measured_facts,
            decision_trace=trace,
        )
