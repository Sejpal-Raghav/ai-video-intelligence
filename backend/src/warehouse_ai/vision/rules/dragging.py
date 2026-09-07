from dataclasses import dataclass
from typing import Any, Sequence

from warehouse_ai.domain.decision_trace import DecisionTrace, PredicateEvaluation
from warehouse_ai.domain.enums import EventType, RiskTier
from warehouse_ai.domain.models import BehaviorRulesConfig, DraggingRulesConfig, TrackObservation
from warehouse_ai.domain.risk import RiskEngine
from warehouse_ai.vision.features import KinematicObservation, compute_reference_dimensions
from warehouse_ai.vision.rules.base import evaluate_event_quality_gate


@dataclass
class EmittedDraggingEvent:
    event_type: EventType
    start_ms: int
    end_ms: int
    keyframe_ms: int
    primary_track_id: int
    associated_track_ids: list[int]
    risk_score: int
    risk_tier: RiskTier
    evidence_quality: float
    is_review_candidate: bool
    measured_facts: dict[str, Any]
    decision_trace: DecisionTrace


class DraggingEngine:
    """Deterministic dragging behavior engine (Section 10.3)."""

    def __init__(
        self,
        package_track_id: int,
        config: BehaviorRulesConfig,
        risk_engine: RiskEngine,
    ) -> None:
        self.track_id = package_track_id
        self.config = config
        self.rule_cfg: DraggingRulesConfig = config.dragging
        self.risk_engine = risk_engine

        # Active state
        self.is_active = False
        self.active_start_ms: int | None = None
        self.active_last_ms: int | None = None
        self.associated_person_ids: set[int] = set()

        # Completed candidate intervals waiting for potential merge (within 500ms)
        self.pending_interval: tuple[int, int, set[int]] | None = None

        # History buffer for sliding 800ms qualification window: list of (timestamp_ms, KinematicObservation, TrackObservation, person_ids)
        self.history: list[tuple[int, KinematicObservation, TrackObservation, list[int]]] = []

    def update(
        self,
        kin: KinematicObservation,
        raw_obs: TrackObservation,
        qualifying_person_ids: list[int],  # persons satisfying ON_FLOOR and NEAR, with no equipment support
        all_track_obs: Sequence[TrackObservation],
        expected_frames: int = 10,
    ) -> EmittedDraggingEvent | None:
        t = kin.timestamp_ms

        # Buffer history (keep up to 1200 ms)
        self.history.append((t, kin, raw_obs, list(qualifying_person_ids)))
        self.history = [h for h in self.history if (t - h[0]) <= 1200]

        has_contact = len(qualifying_person_ids) > 0
        horiz_speed = abs(kin.vx_hps)

        if not self.is_active:
            # Check merge timeout on pending interval
            emitted_event: EmittedDraggingEvent | None = None
            if self.pending_interval is not None:
                p_start, p_end, p_persons = self.pending_interval
                if (t - p_end) > self.rule_cfg.merge_gap_ms:
                    emitted_event = self._finalize_event(p_start, p_end, p_persons, all_track_obs, expected_frames)
                    self.pending_interval = None

            # Check if sliding 800ms window qualifies
            if self._check_qualification_window(t):
                # Candidate begins!
                qual_start = self._get_window_start(t, self.rule_cfg.qualification_window_ms)
                if self.pending_interval is not None and (qual_start - self.pending_interval[1]) <= self.rule_cfg.merge_gap_ms:
                    # Merge with pending interval
                    self.active_start_ms = self.pending_interval[0]
                    self.associated_person_ids.update(self.pending_interval[2])
                    self.pending_interval = None
                else:
                    self.active_start_ms = qual_start

                self.is_active = True
                self.active_last_ms = t
                self.associated_person_ids.update(qualifying_person_ids)

            return emitted_event

        else:
            # Currently active: remains active while conditions 1-3 hold and horizontal speed > 0.20 h/s
            if has_contact and horiz_speed >= self.rule_cfg.active_minimum_horizontal_speed_hps:
                self.active_last_ms = t
                self.associated_person_ids.update(qualifying_person_ids)
            else:
                # Inactive check (ends after 400ms of inactivity)
                if self.active_last_ms and (t - self.active_last_ms) >= self.rule_cfg.end_inactivity_ms:
                    self.is_active = False
                    start_ms = self.active_start_ms or self.active_last_ms
                    end_ms = self.active_last_ms
                    self.pending_interval = (start_ms, end_ms, set(self.associated_person_ids))
                    self.active_start_ms = None
                    self.active_last_ms = None
                    self.associated_person_ids.clear()

            return None

    def flush(
        self,
        all_track_obs: Sequence[TrackObservation],
        expected_frames: int = 10,
    ) -> EmittedDraggingEvent | None:
        """Flush pending interval at end of video."""
        if self.is_active and self.active_start_ms and self.active_last_ms:
            start_ms = self.active_start_ms
            end_ms = self.active_last_ms
            persons = set(self.associated_person_ids)
            self.is_active = False
            return self._finalize_event(start_ms, end_ms, persons, all_track_obs, expected_frames)

        if self.pending_interval is not None:
            p_start, p_end, p_persons = self.pending_interval
            self.pending_interval = None
            return self._finalize_event(p_start, p_end, p_persons, all_track_obs, expected_frames)

        return None

    def _get_window_start(self, current_t: int, window_ms: int) -> int:
        window = [h for h in self.history if (current_t - h[0]) <= window_ms]
        return window[0][0] if window else current_t

    def _check_qualification_window(self, current_t: int) -> bool:
        window = [h for h in self.history if (current_t - h[0]) <= self.rule_cfg.qualification_window_ms]
        if len(window) < 4:
            return False

        # Must have qualifying persons throughout window
        if not any(len(h[3]) > 0 for h in window):
            return False

        first_kin = window[0][1]
        last_kin = window[-1][1]
        raw_obs = [h[2] for h in window]
        w_ref, h_ref = compute_reference_dimensions(raw_obs)

        # 4. Absolute horizontal displacement >= 1.00 w_ref
        horiz_disp_w = abs(last_kin.cx_smooth - first_kin.cx_smooth) / w_ref
        if horiz_disp_w < self.rule_cfg.minimum_horizontal_displacement_w:
            return False

        # 5. Absolute vertical displacement <= 0.25 h_ref
        vert_disp_h = abs(last_kin.cy_smooth - first_kin.cy_smooth) / h_ref
        if vert_disp_h > self.rule_cfg.maximum_vertical_displacement_h:
            return False

        # 6. Directional agreement >= 70% with >= 3 qualifying increments (abs(Δcx) > 0.02 * w_ref)
        left_count = 0
        right_count = 0
        deadband = self.rule_cfg.direction_increment_deadband_w * w_ref

        for i in range(len(window) - 1):
            dcx = window[i + 1][1].cx_smooth - window[i][1].cx_smooth
            if abs(dcx) > deadband:
                if dcx > 0:
                    right_count += 1
                else:
                    left_count += 1

        total_increments = left_count + right_count
        if total_increments < self.rule_cfg.minimum_direction_increments:
            return False

        agreement = max(left_count, right_count) / float(total_increments)
        return agreement >= self.rule_cfg.minimum_direction_agreement

    def _finalize_event(
        self,
        start_ms: int,
        end_ms: int,
        persons: set[int],
        all_track_obs: Sequence[TrackObservation],
        expected_frames: int,
    ) -> EmittedDraggingEvent | None:
        duration_ms = end_ms - start_ms
        # Duration under 800 ms never emits (Section 10.3)
        if duration_ms < self.rule_cfg.qualification_window_ms:
            return None

        duration_s = duration_ms / 1000.0
        keyframe_ms = start_ms + duration_ms // 2

        # Quality gate
        q_res = evaluate_event_quality_gate(all_track_obs, expected_frames, self.config.common)

        measured_facts = {
            "duration_seconds": round(duration_s, 2),
            "start_ms": start_ms,
            "end_ms": end_ms,
            "associated_person_ids": sorted(list(persons)),
        }

        # Calculate risk score
        risk_res = self.risk_engine.calculate(
            event_type=EventType.DRAGGING,
            duration_seconds=duration_s,
            metadata=measured_facts,
        )

        trace = DecisionTrace(
            event_type=EventType.DRAGGING.value,
            primary_track_id=self.track_id,
            associated_track_ids=sorted(list(persons)),
            start_ms=start_ms,
            end_ms=end_ms,
            keyframe_ms=keyframe_ms,
            track_coverage=q_res.track_coverage,
            interpolation_fraction=q_res.interpolation_fraction,
            median_detection_confidence=q_res.median_confidence,
            track_quality=q_res.track_quality,
            evidence_quality=q_res.evidence_quality,
            measured_facts=measured_facts,
            state_transitions=[],
            evaluations=q_res.evaluations,
            risk_score=risk_res.score,
            risk_tier=risk_res.tier.value,
            explanation=risk_res.explanation,
            formula_breakdown=risk_res.formula_breakdown,
        )

        return EmittedDraggingEvent(
            event_type=EventType.DRAGGING,
            start_ms=start_ms,
            end_ms=end_ms,
            keyframe_ms=keyframe_ms,
            primary_track_id=self.track_id,
            associated_track_ids=sorted(list(persons)),
            risk_score=risk_res.score,
            risk_tier=risk_res.tier,
            evidence_quality=q_res.evidence_quality,
            is_review_candidate=(not q_res.passed),
            measured_facts=measured_facts,
            decision_trace=trace,
        )
