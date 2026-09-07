import pytest

from warehouse_ai.domain.models import SupportRegionConfig, TrackObservation, ZoneConfig, ZoneKind, ZoneSeverity
from warehouse_ai.vision.features import (
    compute_reference_dimensions,
    compute_smoothed_centers,
    eval_near,
    eval_on_floor,
    eval_supported_by,
    eval_visible_support_ratio,
    extract_track_kinematics,
    point_in_polygon,
)


def test_smoothed_centers():
    obs = [
        TrackObservation(track_id=1, class_id="package", confidence=0.9, bbox_xyxy_norm=(0.1, 0.1, 0.3, 0.3)),
        TrackObservation(track_id=1, class_id="package", confidence=0.9, bbox_xyxy_norm=(0.12, 0.12, 0.32, 0.32)),
        TrackObservation(track_id=1, class_id="package", confidence=0.9, bbox_xyxy_norm=(0.14, 0.14, 0.34, 0.34)),
    ]
    smoothed = compute_smoothed_centers(obs)
    assert len(smoothed) == 3
    # Center of obs[1] is (0.22, 0.22)
    assert smoothed[1] == (0.22, 0.22)


def test_reference_dimensions():
    obs = [
        TrackObservation(track_id=1, class_id="package", confidence=0.9, bbox_xyxy_norm=(0.1, 0.1, 0.3, 0.4)),  # w=0.2, h=0.3
        TrackObservation(track_id=1, class_id="package", confidence=0.9, bbox_xyxy_norm=(0.1, 0.1, 0.3, 0.4)),
    ]
    w_ref, h_ref = compute_reference_dimensions(obs)
    assert w_ref == 0.2
    assert h_ref == 0.3


def test_kinematics_velocity_downward():
    # Package dropping downwards: cy moves from 0.2 to 0.4 in 0.1s with h_ref = 0.2
    obs = [
        TrackObservation(track_id=1, class_id="package", confidence=0.9, bbox_xyxy_norm=(0.1, 0.1, 0.3, 0.3)),  # cy=0.2
        TrackObservation(track_id=1, class_id="package", confidence=0.9, bbox_xyxy_norm=(0.1, 0.3, 0.3, 0.5)),  # cy=0.4
    ]
    timestamps = [0, 100]
    kin = extract_track_kinematics(obs, timestamps)
    assert len(kin) == 2
    # Positive vy_hps indicates downward motion (Section 9.1 rule 7)
    assert kin[0].vy_hps > 0


def test_near_predicate():
    # Box diagonal = sqrt(0.2^2 + 0.2^2) = 0.2828 -> threshold = 1.5 * 0.2828 = 0.424
    pkg_box = (0.2, 0.2, 0.4, 0.4)
    person_near = (0.3, 0.2, 0.5, 0.8)
    person_far = (0.7, 0.7, 0.9, 0.9)

    res_near = eval_near(person_near, pkg_box)
    assert res_near.passed is True

    res_far = eval_near(person_far, pkg_box)
    assert res_far.passed is False


def test_supported_by_predicate():
    pkg_box = (0.2, 0.4, 0.4, 0.6)  # bottom at 0.6, w=0.2, h=0.2
    equip_box = (0.15, 0.55, 0.45, 0.9)  # top at 0.55, bottom at 0.9
    res = eval_supported_by(pkg_box, equip_box)
    assert res.passed is True


def test_on_floor_predicate():
    floor_poly = [(0.0, 0.5), (1.0, 0.5), (1.0, 1.0), (0.0, 1.0)]
    pkg_box = (0.2, 0.7, 0.4, 0.9)  # bottom at 0.9
    person_box = (0.4, 0.3, 0.6, 0.92)  # bottom at 0.92, h=0.62 -> tol = 0.062, dy = 0.02

    res = eval_on_floor(pkg_box, person_box, floor_poly)
    assert res.passed is True


def test_visible_support_ratio():
    # Support polygon: top of pallet from x=0.1 to 0.5, y=0.5 to 0.8
    support = SupportRegionConfig(
        id="pallet-1",
        label="Pallet Top",
        polygon=[(0.1, 0.5), (0.5, 0.5), (0.5, 0.8), (0.1, 0.8)],
    )
    # Fully on pallet: package from x=0.2 to 0.4, y=0.4 to 0.6 (footprint from y=0.57 to 0.6)
    pkg_on = (0.2, 0.4, 0.4, 0.6)
    ratio_on, reg_on = eval_visible_support_ratio(pkg_on, [support])
    assert ratio_on >= 0.95
    assert reg_on is not None

    # Hanging off pallet: package x=0.4 to 0.6 (half overhang outside x=0.5)
    pkg_overhang = (0.4, 0.4, 0.6, 0.6)
    ratio_hang, reg_hang = eval_visible_support_ratio(pkg_overhang, [support])
    assert 0.40 <= ratio_hang <= 0.60
