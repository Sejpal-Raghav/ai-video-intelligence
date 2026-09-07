from dataclasses import dataclass
from typing import Any, Sequence

from warehouse_ai.domain.decision_trace import DecisionTrace
from warehouse_ai.domain.enums import EventType, RiskTier, ZoneKind, ZoneSeverity
from warehouse_ai.domain.models import BehaviorRulesConfig, CameraProfile, PlacementRulesConfig, TrackObservation
from warehouse_ai.domain.risk import RiskEngine
from warehouse_ai.vision.features import KinematicObservation, eval_in_zone, eval_visible_support_ratio
from warehouse_ai.vision.rules.base import evaluate_event_quality_gate


@dataclass
class EmittedPlacementEvent:
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


class PlacementEngine:
    """Deterministic placement engine for PROHIBITED_ZONE and VISIBLE_SUPPORT_OVERHANG (Section 10.4)."""

    def __init__(
        self,
        package_track_id: int,
        config: BehaviorRulesConfig,
        camera_profile: CameraProfile,
        risk_engine: RiskEngine,
    ) -> None:
        self.track_id = package_track_id
        self.config = config
        self.rule_cfg: PlacementRulesConfig = config.placement
        self.camera_profile = camera_profile
        self.risk_engine = risk_engine

        # Prohibited zone state tracking
        self.in_prohibited_start_ms: int | None = None
        self.prohibited_last_seen_ms: int | None = None
        self.active_prohibited_zone_id: str | None = None
        self.active_prohibited_severity: ZoneSeverity = ZoneSeverity.NORMAL
        self.prohibited_emitted = False

        # Support overhang state tracking
        self.overhang_start_ms: int | None = None
        self.overhang_last_seen_ms: int | None = None
        self.min_observed_support_ratio: float = 1.0
        self.overhang_emitted = False

    def update(
        self,
        kin: KinematicObservation,
        raw_obs: TrackObservation,
        all_track_obs: Sequence[TrackObservation],
        expected_frames: int = 10,
    ) -> list[EmittedPlacementEvent]:
        events: list[EmittedPlacementEvent] = []
        t = kin.timestamp_ms

        # Evaluates only package tracks whose total speed <= 0.25 h/s (Section 10.4)
        if kin.speed_hps > self.rule_cfg.stationary_maximum_speed_hps:
            # Package is moving: reset stationary dwell trackers
            self._handle_moving_reset(t, all_track_obs, expected_frames, events)
            return events

        # 1. Check prohibited zones
        prohibited_zones = [z for z in self.camera_profile.zones if z.kind == ZoneKind.PROHIBITED]
        inside_prohibited = False
        current_zone_severity = ZoneSeverity.NORMAL
        current_zone_id = ""

        for zone in prohibited_zones:
            eval_res = eval_in_zone(raw_obs.bbox_xyxy_norm, zone, pkg_id=self.track_id)
            if eval_res.passed:
                inside_prohibited = True
                current_zone_id = zone.id
                current_zone_severity = zone.severity
                break

        if inside_prohibited:
            self.prohibited_last_seen_ms = t
            if self.in_prohibited_start_ms is None:
                self.in_prohibited_start_ms = t
                self.active_prohibited_zone_id = current_zone_id
                self.active_prohibited_severity = current_zone_severity
            elif (t - self.in_prohibited_start_ms) >= self.rule_cfg.prohibited_zone_dwell_ms and not self.prohibited_emitted:
                # Dwell passed: emit PROHIBITED_ZONE event
                ev = self._emit_prohibited_event(t, all_track_obs, expected_frames)
                events.append(ev)
                self.prohibited_emitted = True
        else:
            if self.prohibited_last_seen_ms and (t - self.prohibited_last_seen_ms) >= self.rule_cfg.prohibited_zone_exit_ms:
                self.in_prohibited_start_ms = None
                self.prohibited_last_seen_ms = None
                self.active_prohibited_zone_id = None
                self.prohibited_emitted = False

        # 2. Check visible support overhang
        if self.camera_profile.support_regions:
            ratio, region = eval_visible_support_ratio(
                raw_obs.bbox_xyxy_norm, self.camera_profile.support_regions, pkg_id=self.track_id
            )
            # Associated with support region and ratio < 0.80 continuously for 500 ms
            if region is not None and ratio < self.rule_cfg.minimum_visible_support_ratio:
                self.overhang_last_seen_ms = t
                self.min_observed_support_ratio = min(self.min_observed_support_ratio, ratio)
                if self.overhang_start_ms is None:
                    self.overhang_start_ms = t
                elif (t - self.overhang_start_ms) >= self.rule_cfg.visible_support_dwell_ms and not self.overhang_emitted:
                    # Emit only if not already in prohibited zone (Section 10.4: do not double-count)
                    if not self.prohibited_emitted:
                        ev = self._emit_overhang_event(t, all_track_obs, expected_frames)
                        events.append(ev)
                        self.overhang_emitted = True
            else:
                if self.overhang_last_seen_ms and (t - self.overhang_last_seen_ms) >= self.rule_cfg.visible_support_exit_ms:
                    self.overhang_start_ms = None
                    self.overhang_last_seen_ms = None
                    self.min_observed_support_ratio = 1.0
                    self.overhang_emitted = False

        return events

    def _handle_moving_reset(
        self,
        t: int,
        all_track_obs: Sequence[TrackObservation],
        expected_frames: int,
        events: list[EmittedPlacementEvent],
    ) -> None:
        self.in_prohibited_start_ms = None
        self.prohibited_last_seen_ms = None
        self.active_prohibited_zone_id = None
        self.prohibited_emitted = False

        self.overhang_start_ms = None
        self.overhang_last_seen_ms = None
        self.min_observed_support_ratio = 1.0
        self.overhang_emitted = False

    def _emit_prohibited_event(
        self,
        t: int,
        all_track_obs: Sequence[TrackObservation],
        expected_frames: int,
    ) -> EmittedPlacementEvent:
        start_ms = self.in_prohibited_start_ms or t
        duration_s = (t - start_ms) / 1000.0
        q_res = evaluate_event_quality_gate(all_track_obs, expected_frames, self.config.common)

        measured_facts = {
            "duration_seconds": round(duration_s, 2),
            "zone_id": self.active_prohibited_zone_id,
            "zone_severity": self.active_prohibited_severity.value,
        }

        risk_res = self.risk_engine.calculate(
            event_type=EventType.PROHIBITED_ZONE,
            duration_seconds=duration_s,
            zone_severity=self.active_prohibited_severity,
            metadata=measured_facts,
        )

        trace = DecisionTrace(
            event_type=EventType.PROHIBITED_ZONE.value,
            primary_track_id=self.track_id,
            associated_track_ids=[],
            start_ms=start_ms,
            end_ms=t,
            keyframe_ms=start_ms + int(duration_s * 500),
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

        return EmittedPlacementEvent(
            event_type=EventType.PROHIBITED_ZONE,
            start_ms=start_ms,
            end_ms=t,
            keyframe_ms=start_ms + int(duration_s * 500),
            primary_track_id=self.track_id,
            risk_score=risk_res.score,
            risk_tier=risk_res.tier,
            evidence_quality=q_res.evidence_quality,
            is_review_candidate=(not q_res.passed),
            measured_facts=measured_facts,
            decision_trace=trace,
        )

    def _emit_overhang_event(
        self,
        t: int,
        all_track_obs: Sequence[TrackObservation],
        expected_frames: int,
    ) -> EmittedPlacementEvent:
        start_ms = self.overhang_start_ms or t
        duration_s = (t - start_ms) / 1000.0
        outside_fraction = max(0.0, 1.0 - self.min_observed_support_ratio)
        q_res = evaluate_event_quality_gate(all_track_obs, expected_frames, self.config.common)

        measured_facts = {
            "duration_seconds": round(duration_s, 2),
            "outside_fraction": round(outside_fraction, 3),
            "visible_support_ratio": round(self.min_observed_support_ratio, 3),
        }

        risk_res = self.risk_engine.calculate(
            event_type=EventType.VISIBLE_SUPPORT_OVERHANG,
            duration_seconds=duration_s,
            outside_fraction=outside_fraction,
            metadata=measured_facts,
        )

        trace = DecisionTrace(
            event_type=EventType.VISIBLE_SUPPORT_OVERHANG.value,
            primary_track_id=self.track_id,
            associated_track_ids=[],
            start_ms=start_ms,
            end_ms=t,
            keyframe_ms=start_ms + int(duration_s * 500),
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

        return EmittedPlacementEvent(
            event_type=EventType.VISIBLE_SUPPORT_OVERHANG,
            start_ms=start_ms,
            end_ms=t,
            keyframe_ms=start_ms + int(duration_s * 500),
            primary_track_id=self.track_id,
            risk_score=risk_res.score,
            risk_tier=risk_res.tier,
            evidence_quality=q_res.evidence_quality,
            is_review_candidate=(not q_res.passed),
            measured_facts=measured_facts,
            decision_trace=trace,
        )
