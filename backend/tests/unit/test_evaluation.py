"""Unit tests for offline evaluation benchmark module matching Blueprint Section 17.1 & 17.2."""

from pathlib import Path
from warehouse_ai.evaluation import (
    EventInterval,
    compute_temporal_iou,
    evaluate_scenario,
    run_evaluation_benchmark,
)


def test_compute_temporal_iou():
    # Identical intervals -> IoU = 1.0
    ev1 = EventInterval("DROP", 1000, 3000)
    ev2 = EventInterval("DROP", 1000, 3000)
    assert compute_temporal_iou(ev1, ev2) == 1.0

    # Half overlap: 1000-2000 and 1500-2500 -> intersection 500, union 1500 -> 0.333
    ev3 = EventInterval("DROP", 1000, 2000)
    ev4 = EventInterval("DROP", 1500, 2500)
    iou = compute_temporal_iou(ev3, ev4)
    assert round(iou, 3) == 0.333

    # Disjoint intervals -> IoU = 0.0
    ev5 = EventInterval("DROP", 1000, 2000)
    ev6 = EventInterval("DROP", 3000, 4000)
    assert compute_temporal_iou(ev5, ev6) == 0.0


def test_evaluate_scenario_control():
    # Control scenario with 0 predictions -> pass
    res_pass = evaluate_scenario("S01_CONTROLLED_PLACE", [], [])
    assert res_pass.is_control is True
    assert res_pass.control_passed is True
    assert res_pass.false_positives == 0

    # Control scenario with 1 false alarm -> fail
    pred = [EventInterval("DROP", 1000, 2000)]
    res_fail = evaluate_scenario("S01_CONTROLLED_PLACE", [], pred)
    assert res_fail.is_control is True
    assert res_fail.control_passed is False
    assert res_fail.false_positives == 1


def test_evaluate_scenario_matching():
    # Ground truth: DROP at 1500-2500
    gt = [EventInterval("DROP", 1500, 2500)]
    # Prediction: DROP at 1600-2600 (IoU = 900 / 1100 = 0.818 >= 0.30)
    pred = [EventInterval("DROP", 1600, 2600)]

    res = evaluate_scenario("S02_LOW_DROP", gt, pred, iou_threshold=0.30)
    assert res.is_control is False
    assert res.true_positives == 1
    assert res.false_positives == 0
    assert res.false_negatives == 0
    assert len(res.matches) == 1


def test_run_evaluation_benchmark():
    annotations_path = Path("data/annotations/events.v1.json")
    assert annotations_path.exists()

    # Synthetic predictions matching ground truth
    preds = {
        "S01_CONTROLLED_PLACE": [],
        "S02_LOW_DROP": [{"event_type": "DROP", "start_ms": 1500, "end_ms": 2600}],
        "S03_HIGH_DROP": [{"event_type": "DROP", "start_ms": 2000, "end_ms": 3400}],
        "S04_LATERAL_THROW": [{"event_type": "FORCEFUL_RELEASE", "start_ms": 4500, "end_ms": 6500}],
        "S05_SUPPORTED_TRANSPORT": [],
        "S06_SHORT_DRAG": [{"event_type": "DRAGGING", "start_ms": 1800, "end_ms": 3200}],
        "S07_PROLONGED_DRAG": [{"event_type": "DRAGGING", "start_ms": 1200, "end_ms": 4500}],
        "S08_CORRECT_PALLET_PLACE": [],
        "S09_PALLET_OVERHANG": [{"event_type": "VISIBLE_SUPPORT_OVERHANG", "start_ms": 2500, "end_ms": 4800}],
        "S10_PROHIBITED_ZONE": [{"event_type": "PROHIBITED_ZONE", "start_ms": 2000, "end_ms": 4200}],
    }

    report = run_evaluation_benchmark(
        annotations_path=annotations_path,
        predictions_by_scenario=preds,
        total_validation_minutes=10.0,
    )

    assert report.total_clips == 10
    assert report.controls_total == 3
    assert report.controls_passed == 3
    assert report.true_positives == 7
    assert report.false_positives == 0
    assert report.false_negatives == 0
    assert report.precision == 1.0
    assert report.recall == 1.0
    assert report.f1_score == 1.0
    assert report.false_alert_rate == 0.0
