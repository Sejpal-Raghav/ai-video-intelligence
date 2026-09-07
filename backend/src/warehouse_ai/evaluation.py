"""Offline evaluation benchmark and metrics computation matching Blueprint Section 17.1 & 17.2."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class EventInterval:
    event_type: str
    start_ms: int
    end_ms: int


@dataclass
class ScenarioResult:
    scenario_id: str
    is_control: bool
    ground_truth_count: int
    prediction_count: int
    true_positives: int
    false_positives: int
    false_negatives: int
    control_passed: bool | None
    matches: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class EvaluationReport:
    schema_version: str = "evaluation-report.v1"
    total_clips: int = 0
    total_duration_minutes: float = 0.0
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    false_alert_rate: float = 0.0
    controls_passed: int = 0
    controls_total: int = 0
    scenarios: list[ScenarioResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "summary": {
                "total_clips": self.total_clips,
                "total_duration_minutes": round(self.total_duration_minutes, 2),
                "true_positives": self.true_positives,
                "false_positives": self.false_positives,
                "false_negatives": self.false_negatives,
                "precision": round(self.precision, 4),
                "recall": round(self.recall, 4),
                "f1_score": round(self.f1_score, 4),
                "false_alert_rate": round(self.false_alert_rate, 4),
                "controls_passed": self.controls_passed,
                "controls_total": self.controls_total,
            },
            "scenarios": [
                {
                    "scenario_id": s.scenario_id,
                    "is_control": s.is_control,
                    "ground_truth_count": s.ground_truth_count,
                    "prediction_count": s.prediction_count,
                    "true_positives": s.true_positives,
                    "false_positives": s.false_positives,
                    "false_negatives": s.false_negatives,
                    "control_passed": s.control_passed,
                    "matches": s.matches,
                }
                for s in self.scenarios
            ],
        }


def compute_temporal_iou(pred: EventInterval, gt: EventInterval) -> float:
    """Compute temporal Intersection-over-Union between two intervals."""
    intersection_start = max(pred.start_ms, gt.start_ms)
    intersection_end = min(pred.end_ms, gt.end_ms)
    intersection = max(0, intersection_end - intersection_start)

    union_start = min(pred.start_ms, gt.start_ms)
    union_end = max(pred.end_ms, gt.end_ms)
    union = max(1, union_end - union_start)

    return intersection / float(union)


def evaluate_scenario(
    scenario_id: str,
    ground_truth_events: list[EventInterval],
    predicted_events: list[EventInterval],
    iou_threshold: float = 0.30,
) -> ScenarioResult:
    """Match predicted events to ground truth greedily by highest temporal IoU >= 0.30."""
    is_control = len(ground_truth_events) == 0

    if is_control:
        fp = len(predicted_events)
        control_passed = (fp == 0)
        return ScenarioResult(
            scenario_id=scenario_id,
            is_control=True,
            ground_truth_count=0,
            prediction_count=len(predicted_events),
            true_positives=0,
            false_positives=fp,
            false_negatives=0,
            control_passed=control_passed,
        )

    # Compute all candidate pairs with temporal IoU >= threshold of the same event_type
    candidate_matches: list[tuple[float, int, int]] = []
    for p_idx, p in enumerate(predicted_events):
        for g_idx, g in enumerate(ground_truth_events):
            if p.event_type == g.event_type:
                iou = compute_temporal_iou(p, g)
                if iou >= iou_threshold:
                    candidate_matches.append((iou, p_idx, g_idx))

    # Sort greedy by descending IoU
    candidate_matches.sort(key=lambda x: x[0], reverse=True)

    matched_preds: set[int] = set()
    matched_gts: set[int] = set()
    matches: list[dict[str, Any]] = []

    for iou, p_idx, g_idx in candidate_matches:
        if p_idx not in matched_preds and g_idx not in matched_gts:
            matched_preds.add(p_idx)
            matched_gts.add(g_idx)
            matches.append({
                "pred_index": p_idx,
                "gt_index": g_idx,
                "event_type": predicted_events[p_idx].event_type,
                "temporal_iou": round(iou, 4),
            })

    tp = len(matched_preds)
    fp = len(predicted_events) - tp
    fn = len(ground_truth_events) - len(matched_gts)

    return ScenarioResult(
        scenario_id=scenario_id,
        is_control=False,
        ground_truth_count=len(ground_truth_events),
        prediction_count=len(predicted_events),
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        control_passed=None,
        matches=matches,
    )


def run_evaluation_benchmark(
    annotations_path: Path | str,
    predictions_by_scenario: dict[str, list[dict[str, Any]]],
    total_validation_minutes: float = 10.0,
    iou_threshold: float = 0.30,
) -> EvaluationReport:
    """Run complete evaluation benchmark across all annotated clips."""
    with open(annotations_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    report = EvaluationReport(
        total_clips=len(data.get("clips", [])),
        total_duration_minutes=total_validation_minutes,
    )

    for clip in data.get("clips", []):
        scenario_id = clip["scenario_id"]
        gt_events = [
            EventInterval(
                event_type=e["event_type"],
                start_ms=e["start_ms"],
                end_ms=e["end_ms"],
            )
            for e in clip.get("expected_events", [])
        ]

        raw_preds = predictions_by_scenario.get(scenario_id, [])
        pred_events = [
            EventInterval(
                event_type=p["event_type"],
                start_ms=p["start_ms"],
                end_ms=p["end_ms"],
            )
            for p in raw_preds
        ]

        res = evaluate_scenario(scenario_id, gt_events, pred_events, iou_threshold=iou_threshold)
        report.scenarios.append(res)

        report.true_positives += res.true_positives
        report.false_positives += res.false_positives
        report.false_negatives += res.false_negatives

        if res.is_control:
            report.controls_total += 1
            if res.control_passed:
                report.controls_passed += 1

    # Precision, Recall, F1
    total_pred = report.true_positives + report.false_positives
    report.precision = (report.true_positives / total_pred) if total_pred > 0 else 0.0

    total_gt = report.true_positives + report.false_negatives
    report.recall = (report.true_positives / total_gt) if total_gt > 0 else 0.0

    if (report.precision + report.recall) > 0:
        report.f1_score = (2 * report.precision * report.recall) / (report.precision + report.recall)
    else:
        report.f1_score = 0.0

    # False alert rate per minute
    if total_validation_minutes > 0:
        report.false_alert_rate = report.false_positives / total_validation_minutes
    else:
        report.false_alert_rate = 0.0

    return report
