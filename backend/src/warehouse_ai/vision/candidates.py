from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class CandidateWindow:
    """Time window proposing high-rate verification for a hero candidate (Section 10.5)."""
    track_id: int
    start_ms: int
    end_ms: int
    padding_ms: int = 2000

    @property
    def padded_start_ms(self) -> int:
        return max(0, self.start_ms - self.padding_ms)

    @property
    def padded_end_ms(self) -> int:
        return self.end_ms + self.padding_ms


def compute_temporal_iou(
    start1: int, end1: int, start2: int, end2: int
) -> float:
    """Compute temporal IoU = intersection_duration / union_duration (Section 17.2)."""
    inter_start = max(start1, start2)
    inter_end = min(end1, end2)
    intersection = max(0, inter_end - inter_start)

    union_start = min(start1, start2)
    union_end = max(end1, end2)
    union = max(1, union_end - union_start)

    return float(intersection) / float(union)


def compute_spatial_box_iou(
    b1: tuple[float, float, float, float], b2: tuple[float, float, float, float]
) -> float:
    """Compute 2D bounding box intersection over union."""
    x1 = max(b1[0], b2[0])
    y1 = max(b1[1], b2[1])
    x2 = min(b1[2], b2[2])
    y2 = min(b1[3], b2[3])

    inter_w = max(0.0, x2 - x1)
    inter_h = max(0.0, y2 - y1)
    inter_area = inter_w * inter_h

    b1_area = (b1[2] - b1[0]) * (b1[3] - b1[1])
    b2_area = (b2[2] - b2[0]) * (b2[3] - b2[1])
    union_area = b1_area + b2_area - inter_area

    if union_area <= 1e-9:
        return 0.0
    return inter_area / union_area
