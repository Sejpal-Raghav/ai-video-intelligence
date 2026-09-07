import math
import statistics
from dataclasses import dataclass
from typing import Sequence

from warehouse_ai.domain.decision_trace import PredicateEvaluation
from warehouse_ai.domain.models import CameraProfile, SupportRegionConfig, TrackObservation, ZoneConfig


@dataclass(frozen=True)
class KinematicObservation:
    """Kinematic observation for a track at a specific time."""
    track_id: int
    timestamp_ms: int
    cx_smooth: float
    cy_smooth: float
    w: float
    h: float
    vx_hps: float
    vy_hps: float
    speed_hps: float
    is_interpolated: bool
    confidence: float
    bbox_xyxy_norm: tuple[float, float, float, float]


def compute_smoothed_centers(
    observations: Sequence[TrackObservation],
) -> list[tuple[float, float]]:
    """Compute 3-observation median smoothed center coordinates (Section 9.1 rule 4)."""
    n = len(observations)
    if n == 0:
        return []

    raw_centers = [
        (
            (obs.bbox_xyxy_norm[0] + obs.bbox_xyxy_norm[2]) / 2.0,
            (obs.bbox_xyxy_norm[1] + obs.bbox_xyxy_norm[3]) / 2.0,
        )
        for obs in observations
    ]

    if n == 1:
        return raw_centers
    if n == 2:
        m_x = (raw_centers[0][0] + raw_centers[1][0]) / 2.0
        m_y = (raw_centers[0][1] + raw_centers[1][1]) / 2.0
        return [(m_x, m_y), (m_x, m_y)]

    smoothed: list[tuple[float, float]] = []
    # First observation: median of available 2 values
    smoothed.append(
        (
            statistics.median([raw_centers[0][0], raw_centers[1][0]]),
            statistics.median([raw_centers[0][1], raw_centers[1][1]]),
        )
    )

    # Middle observations: median of 3 values
    for i in range(1, n - 1):
        smoothed.append(
            (
                statistics.median([raw_centers[i - 1][0], raw_centers[i][0], raw_centers[i + 1][0]]),
                statistics.median([raw_centers[i - 1][1], raw_centers[i][1], raw_centers[i + 1][1]]),
            )
        )

    # Last observation: median of available 2 values
    smoothed.append(
        (
            statistics.median([raw_centers[n - 2][0], raw_centers[n - 1][0]]),
            statistics.median([raw_centers[n - 2][1], raw_centers[n - 1][1]]),
        )
    )

    return [(round(x, 6), round(y, 6)) for x, y in smoothed]


def compute_reference_dimensions(
    observations: Sequence[TrackObservation],
) -> tuple[float, float]:
    """Compute median non-interpolated width and height (w_ref, h_ref) (Section 9.1 rule 5)."""
    non_interp = [obs for obs in observations if not obs.is_interpolated]
    if not non_interp:
        non_interp = list(observations)
    if not non_interp:
        return 0.0, 0.0

    widths = [obs.bbox_xyxy_norm[2] - obs.bbox_xyxy_norm[0] for obs in non_interp]
    heights = [obs.bbox_xyxy_norm[3] - obs.bbox_xyxy_norm[1] for obs in non_interp]

    w_ref = float(statistics.median(widths))
    h_ref = float(statistics.median(heights))

    return max(1e-6, round(w_ref, 6)), max(1e-6, round(h_ref, 6))


def extract_track_kinematics(
    observations: Sequence[TrackObservation],
    timestamps_ms: Sequence[int],
) -> list[KinematicObservation]:
    """Extract smoothed kinematics, velocities, and speeds for a single track (Section 9.1)."""
    n = len(observations)
    if n == 0:
        return []

    w_ref, h_ref = compute_reference_dimensions(observations)
    smoothed_centers = compute_smoothed_centers(observations)

    kinematics: list[KinematicObservation] = []

    for i in range(n):
        obs = observations[i]
        t_i = timestamps_ms[i]
        cx, cy = smoothed_centers[i]
        w = obs.bbox_xyxy_norm[2] - obs.bbox_xyxy_norm[0]
        h = obs.bbox_xyxy_norm[3] - obs.bbox_xyxy_norm[1]

        # Interpolated observations must not establish peak speed or impact (Rule 3)
        if obs.is_interpolated:
            kinematics.append(
                KinematicObservation(
                    track_id=obs.track_id,
                    timestamp_ms=t_i,
                    cx_smooth=cx,
                    cy_smooth=cy,
                    w=w,
                    h=h,
                    vx_hps=0.0,
                    vy_hps=0.0,
                    speed_hps=0.0,
                    is_interpolated=True,
                    confidence=obs.confidence,
                    bbox_xyxy_norm=obs.bbox_xyxy_norm,
                )
            )
            continue

        # Compute central-difference velocity where adjacent non-interpolated exist within 200 ms
        vx_hps = 0.0
        vy_hps = 0.0

        has_prev = (
            i > 0
            and not observations[i - 1].is_interpolated
            and (t_i - timestamps_ms[i - 1]) <= 200
        )
        has_next = (
            i < n - 1
            and not observations[i + 1].is_interpolated
            and (timestamps_ms[i + 1] - t_i) <= 200
        )

        if has_prev and has_next and (timestamps_ms[i + 1] - timestamps_ms[i - 1]) <= 200:
            dt_s = (timestamps_ms[i + 1] - timestamps_ms[i - 1]) / 1000.0
            if dt_s > 0:
                dcx = smoothed_centers[i + 1][0] - smoothed_centers[i - 1][0]
                dcy = smoothed_centers[i + 1][1] - smoothed_centers[i - 1][1]
                vx_hps = dcx / (h_ref * dt_s)
                vy_hps = dcy / (h_ref * dt_s)
        elif has_next:
            dt_s = (timestamps_ms[i + 1] - t_i) / 1000.0
            if dt_s > 0:
                dcx = smoothed_centers[i + 1][0] - cx
                dcy = smoothed_centers[i + 1][1] - cy
                vx_hps = dcx / (h_ref * dt_s)
                vy_hps = dcy / (h_ref * dt_s)
        elif has_prev:
            dt_s = (t_i - timestamps_ms[i - 1]) / 1000.0
            if dt_s > 0:
                dcx = cx - smoothed_centers[i - 1][0]
                dcy = cy - smoothed_centers[i - 1][1]
                vx_hps = dcx / (h_ref * dt_s)
                vy_hps = dcy / (h_ref * dt_s)

        speed_hps = math.sqrt(vx_hps**2 + vy_hps**2)

        kinematics.append(
            KinematicObservation(
                track_id=obs.track_id,
                timestamp_ms=t_i,
                cx_smooth=cx,
                cy_smooth=cy,
                w=w,
                h=h,
                vx_hps=round(vx_hps, 4),
                vy_hps=round(vy_hps, 4),
                speed_hps=round(speed_hps, 4),
                is_interpolated=False,
                confidence=obs.confidence,
                bbox_xyxy_norm=obs.bbox_xyxy_norm,
            )
        )

    return kinematics


# --- Geometry & Relationship Predicates (Section 9.2) ---

def point_in_polygon(px: float, py: float, polygon: Sequence[tuple[float, float]]) -> bool:
    """Ray casting point-in-polygon test."""
    n = len(polygon)
    if n < 3:
        return False
    inside = False
    p1x, p1y = polygon[0]
    for i in range(n + 1):
        p2x, p2y = polygon[i % n]
        if py > min(p1y, p2y):
            if py <= max(p1y, p2y):
                if px <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (py - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or px <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside


def polygon_area(pts: Sequence[tuple[float, float]]) -> float:
    """Shoelace formula for polygon area."""
    n = len(pts)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += pts[i][0] * pts[j][1] - pts[j][0] * pts[i][1]
    return abs(area) / 2.0


def clip_polygon_by_halfplane(
    subject_poly: list[tuple[float, float]],
    cp1: tuple[float, float],
    cp2: tuple[float, float],
) -> list[tuple[float, float]]:
    """Sutherland-Hodgman step clipping subject_poly by directed edge cp1 -> cp2."""
    if not subject_poly:
        return []

    def is_inside(p: tuple[float, float]) -> bool:
        # Cross product (cp2 - cp1) x (p - cp1) >= 0 (left of directed edge)
        return (cp2[0] - cp1[0]) * (p[1] - cp1[1]) - (cp2[1] - cp1[1]) * (p[0] - cp1[0]) >= -1e-9

    def intersection(p1: tuple[float, float], p2: tuple[float, float]) -> tuple[float, float]:
        dc = (cp1[0] - cp2[0], cp1[1] - cp2[1])
        dp = (p1[0] - p2[0], p1[1] - p2[1])
        n1 = cp1[0] * cp2[1] - cp1[1] * cp2[0]
        n2 = p1[0] * p2[1] - p1[1] * p2[0]
        denom = dc[0] * dp[1] - dc[1] * dp[0]
        if abs(denom) < 1e-12:
            return p1
        x = (n1 * dp[0] - n2 * dc[0]) / denom
        y = (n1 * dp[1] - n2 * dc[1]) / denom
        return (x, y)

    output_list: list[tuple[float, float]] = []
    s = subject_poly[-1]
    for e in subject_poly:
        if is_inside(e):
            if not is_inside(s):
                output_list.append(intersection(s, e))
            output_list.append(e)
        elif is_inside(s):
            output_list.append(intersection(s, e))
        s = e
    return output_list


def clip_convex_polygons(
    poly1: Sequence[tuple[float, float]],
    poly2: Sequence[tuple[float, float]],
) -> list[tuple[float, float]]:
    """Clip convex poly1 by convex poly2 using Sutherland-Hodgman."""
    output = list(poly1)
    n = len(poly2)
    for i in range(n):
        cp1 = poly2[i]
        cp2 = poly2[(i + 1) % n]
        output = clip_polygon_by_halfplane(output, cp1, cp2)
        if not output:
            break
    return output


def eval_near(
    person_box: tuple[float, float, float, float],
    pkg_box: tuple[float, float, float, float],
    threshold_diag_mult: float = 1.50,
    person_id: int = 0,
    pkg_id: int = 0,
) -> PredicateEvaluation:
    """NEAR(person, package): center distance <= threshold_diag_mult * package_diagonal (Section 9.2)."""
    p_cx = (person_box[0] + person_box[2]) / 2.0
    p_cy = (person_box[1] + person_box[3]) / 2.0
    k_cx = (pkg_box[0] + pkg_box[2]) / 2.0
    k_cy = (pkg_box[1] + pkg_box[3]) / 2.0

    pkg_w = pkg_box[2] - pkg_box[0]
    pkg_h = pkg_box[3] - pkg_box[1]
    pkg_diag = math.hypot(pkg_w, pkg_h)
    thresh = threshold_diag_mult * pkg_diag

    dist = math.hypot(p_cx - k_cx, p_cy - k_cy)
    passed = dist <= thresh

    return PredicateEvaluation(
        name="NEAR",
        evaluated_value=round(dist, 4),
        threshold=round(thresh, 4),
        passed=passed,
        contributing_track_ids=[person_id, pkg_id],
    )


def eval_co_moving(
    person_kin: KinematicObservation,
    pkg_kin: KinematicObservation,
    min_speed_hps: float = 0.15,
    min_cosine: float = 0.70,
) -> PredicateEvaluation:
    """CO_MOVING(person, package): both speeds > min_speed and cosine >= min_cosine (Section 9.2)."""
    p_speed = person_kin.speed_hps
    k_speed = pkg_kin.speed_hps

    if p_speed < min_speed_hps or k_speed < min_speed_hps:
        return PredicateEvaluation(
            name="CO_MOVING",
            evaluated_value=round(min(p_speed, k_speed), 4),
            threshold=min_speed_hps,
            passed=False,
            contributing_track_ids=[person_kin.track_id, pkg_kin.track_id],
        )

    # Cosine similarity
    dot = person_kin.vx_hps * pkg_kin.vx_hps + person_kin.vy_hps * pkg_kin.vy_hps
    cos_sim = dot / (p_speed * k_speed) if (p_speed * k_speed) > 1e-9 else 0.0
    passed = cos_sim >= min_cosine

    return PredicateEvaluation(
        name="CO_MOVING",
        evaluated_value=round(cos_sim, 4),
        threshold=min_cosine,
        passed=passed,
        contributing_track_ids=[person_kin.track_id, pkg_kin.track_id],
    )


def eval_supported_by(
    pkg_box: tuple[float, float, float, float],
    equip_box: tuple[float, float, float, float],
    min_overlap_ratio: float = 0.60,
    top_tol_h: float = 0.20,
    bottom_tol_h: float = 0.10,
    pkg_id: int = 0,
    equip_id: int = 0,
) -> PredicateEvaluation:
    """SUPPORTED_BY(package, equipment): horizontal overlap >= 0.60 and package bottom within vertical range."""
    px1, py1, px2, py2 = pkg_box
    ex1, ey1, ex2, ey2 = equip_box

    pkg_w = px2 - px1
    pkg_h = py2 - py1

    # Horizontal overlap
    overlap_x = max(0.0, min(px2, ex2) - max(px1, ex1))
    overlap_ratio = overlap_x / pkg_w if pkg_w > 0 else 0.0

    # Vertical position check
    y_min = ey1 - top_tol_h * pkg_h
    y_max = ey2 + bottom_tol_h * pkg_h
    y_in_range = (y_min <= py2 <= y_max)

    passed = (overlap_ratio >= min_overlap_ratio) and y_in_range

    return PredicateEvaluation(
        name="SUPPORTED_BY",
        evaluated_value=round(overlap_ratio, 4),
        threshold=min_overlap_ratio,
        passed=passed,
        contributing_track_ids=[pkg_id, equip_id],
        metadata={"y_in_range": y_in_range, "py2": py2, "y_min": y_min, "y_max": y_max},
    )


def eval_on_floor(
    pkg_box: tuple[float, float, float, float],
    person_box: tuple[float, float, float, float],
    floor_polygon: Sequence[tuple[float, float]],
    bottom_tol_person_h: float = 0.10,
    pkg_id: int = 0,
    person_id: int = 0,
) -> PredicateEvaluation:
    """ON_FLOOR(package, person): both bottom-centers in floor polygon and vertical difference <= tol."""
    pkg_bc = ((pkg_box[0] + pkg_box[2]) / 2.0, pkg_box[3])
    person_bc = ((person_box[0] + person_box[2]) / 2.0, person_box[3])

    pkg_in_floor = point_in_polygon(pkg_bc[0], pkg_bc[1], floor_polygon)
    person_in_floor = point_in_polygon(person_bc[0], person_bc[1], floor_polygon)

    person_h = person_box[3] - person_box[1]
    dy = abs(pkg_box[3] - person_box[3])
    tol = bottom_tol_person_h * person_h

    passed = pkg_in_floor and person_in_floor and (dy <= tol)

    return PredicateEvaluation(
        name="ON_FLOOR",
        evaluated_value=round(dy, 4),
        threshold=round(tol, 4),
        passed=passed,
        contributing_track_ids=[pkg_id, person_id],
        metadata={"pkg_in_floor": pkg_in_floor, "person_in_floor": person_in_floor},
    )


def eval_in_zone(
    pkg_box: tuple[float, float, float, float],
    zone: ZoneConfig,
    pkg_id: int = 0,
) -> PredicateEvaluation:
    """IN_ZONE(package, zone): package bottom-center inside zone polygon."""
    pkg_bc = ((pkg_box[0] + pkg_box[2]) / 2.0, pkg_box[3])
    passed = point_in_polygon(pkg_bc[0], pkg_bc[1], zone.polygon)

    return PredicateEvaluation(
        name="IN_ZONE",
        evaluated_value=f"({pkg_bc[0]:.3f}, {pkg_bc[1]:.3f})",
        threshold=zone.id,
        passed=passed,
        contributing_track_ids=[pkg_id],
        metadata={"zone_kind": zone.kind.value, "zone_severity": zone.severity.value},
    )


def eval_visible_support_ratio(
    pkg_box: tuple[float, float, float, float],
    support_regions: Sequence[SupportRegionConfig],
    bottom_fraction: float = 0.15,
    pkg_id: int = 0,
) -> tuple[float, SupportRegionConfig | None]:
    """Calculate VISIBLE_SUPPORT_RATIO (Section 9.2).
    
    Approximates package contact footprint as bottom 15% of box and divides footprint
    area intersecting the nearest configured convex support polygon by total footprint area,
    clamped to [0, 1].
    """
    if not support_regions:
        return 1.0, None  # Undefined/disabled when no support polygon calibrated

    px1, py1, px2, py2 = pkg_box
    pkg_h = py2 - py1
    foot_y = py2 - bottom_fraction * pkg_h

    # Footprint rectangle as polygon vertices
    footprint_poly = [
        (px1, foot_y),
        (px2, foot_y),
        (px2, py2),
        (px1, py2),
    ]
    footprint_total_area = polygon_area(footprint_poly)
    if footprint_total_area <= 1e-9:
        return 1.0, None

    max_ratio = 0.0
    best_region: SupportRegionConfig | None = None

    for region in support_regions:
        intersection = clip_convex_polygons(footprint_poly, region.polygon)
        inter_area = polygon_area(intersection)
        ratio = max(0.0, min(1.0, inter_area / footprint_total_area))
        if ratio > max_ratio:
            max_ratio = ratio
            best_region = region

    return round(max_ratio, 4), best_region
