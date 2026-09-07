from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
import statistics
from typing import Any, Sequence

from warehouse_ai.domain.decision_trace import PredicateEvaluation
from warehouse_ai.domain.models import CommonRulesConfig, TrackObservation


def round_half_up_float(val: float, decimals: int = 3) -> float:
    """Round float to specified decimal places with exact halves rounded upward."""
    d = Decimal(str(val))
    target = Decimal("10") ** -decimals
    return float(d.quantize(target, rounding=ROUND_HALF_UP))


@dataclass(frozen=True)
class QualityGateResult:
    passed: bool
    track_coverage: float
    interpolation_fraction: float
    median_confidence: float
    track_quality: float
    evidence_quality: float
    boundary_touch_fraction: float
    evaluations: list[PredicateEvaluation] = field(default_factory=list)


def evaluate_event_quality_gate(
    observations: Sequence[TrackObservation],
    expected_inference_frames: int,
    config: CommonRulesConfig,
) -> QualityGateResult:
    """Evaluate common event-quality gate over evidence window (Section 10.1)."""
    if expected_inference_frames <= 0:
        expected_inference_frames = max(1, len(observations))

    total_obs = len(observations)
    non_interp = [obs for obs in observations if not obs.is_interpolated]
    non_interp_count = len(non_interp)

    # Track coverage = observed_inference_frames / expected_inference_frames
    coverage = min(1.0, total_obs / float(expected_inference_frames))

    # Interpolation fraction = interpolated_obs / expected_inference_frames
    interp_count = total_obs - non_interp_count
    interp_fraction = interp_count / float(expected_inference_frames)

    # Median package detection confidence over non-interpolated
    if non_interp:
        confidences = [obs.confidence for obs in non_interp]
        median_conf = float(statistics.median(confidences))
    else:
        median_conf = 0.0

    # Boundary touching fraction: any box edge within boundary_margin_norm of frame edge
    margin = config.boundary_margin_norm
    boundary_touch_count = 0
    for obs in observations:
        x1, y1, x2, y2 = obs.bbox_xyxy_norm
        if x1 <= margin or y1 <= margin or x2 >= (1.0 - margin) or y2 >= (1.0 - margin):
            boundary_touch_count += 1
    boundary_fraction = boundary_touch_count / float(total_obs) if total_obs > 0 else 0.0

    # Formulations from Section 10.1
    # track_quality = clamp(0.70*coverage + 0.30*(1-interpolation_fraction), 0, 1)
    raw_track_q = 0.70 * coverage + 0.30 * (1.0 - interp_fraction)
    track_quality = max(0.0, min(1.0, raw_track_q))

    # evidence_quality = round_half_up(0.60*median_detection_confidence + 0.40*track_quality, 3 decimal places)
    raw_evidence_q = 0.60 * median_conf + 0.40 * track_quality
    evidence_quality = round_half_up_float(raw_evidence_q, 3)

    # Evaluate individual gates
    p_non_interp = PredicateEvaluation(
        name="min_non_interpolated_observations",
        evaluated_value=non_interp_count,
        threshold=config.minimum_non_interpolated_observations,
        passed=(non_interp_count >= config.minimum_non_interpolated_observations),
    )
    p_conf = PredicateEvaluation(
        name="median_detection_confidence",
        evaluated_value=round(median_conf, 4),
        threshold=config.minimum_median_detection_confidence,
        passed=(median_conf >= config.minimum_median_detection_confidence),
    )
    p_coverage = PredicateEvaluation(
        name="track_coverage",
        evaluated_value=round(coverage, 4),
        threshold=config.minimum_track_coverage,
        passed=(coverage >= config.minimum_track_coverage),
    )
    p_interp = PredicateEvaluation(
        name="interpolation_fraction",
        evaluated_value=round(interp_fraction, 4),
        threshold=config.maximum_interpolation_fraction,
        passed=(interp_fraction <= config.maximum_interpolation_fraction),
    )
    p_boundary = PredicateEvaluation(
        name="boundary_fraction",
        evaluated_value=round(boundary_fraction, 4),
        threshold=config.maximum_boundary_fraction,
        passed=(boundary_fraction <= config.maximum_boundary_fraction),
    )

    evaluations = [p_non_interp, p_conf, p_coverage, p_interp, p_boundary]
    passed = all(e.passed for e in evaluations)

    return QualityGateResult(
        passed=passed,
        track_coverage=round(coverage, 4),
        interpolation_fraction=round(interp_fraction, 4),
        median_confidence=round(median_conf, 4),
        track_quality=round(track_quality, 4),
        evidence_quality=evidence_quality,
        boundary_touch_fraction=round(boundary_fraction, 4),
        evaluations=evaluations,
    )
