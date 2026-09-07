from typing import Iterator, Sequence

from warehouse_ai.domain.models import Frame


class FrameSampler:
    """PTS-based frame sampler implementing Section 9.1 rule 1.
    
    Samples decoded frames at target FPS using PTS:
    Selects the first decoded frame whose PTS is at least next_target_ms,
    then increments next_target_ms by target step (e.g. 100 ms for 10 FPS).
    Never duplicates a source frame.
    """

    def __init__(self, target_fps: int = 10) -> None:
        if target_fps <= 0:
            raise ValueError(f"target_fps must be positive, got {target_fps}")
        self.target_fps = target_fps
        self.step_ms = 1000.0 / target_fps

    def sample(self, frames: Iterator[Frame]) -> Iterator[Frame]:
        next_target_ms = 0.0
        for frame in frames:
            if frame.timestamp_ms >= next_target_ms:
                yield frame
                next_target_ms += self.step_ms


def validate_normalized_bbox(
    x1: float, y1: float, x2: float, y2: float
) -> tuple[float, float, float, float]:
    """Validate and clamp bounding box coordinates to [0, 1] with x1 < x2 and y1 < y2."""
    clamped_x1 = max(0.0, min(1.0, float(x1)))
    clamped_y1 = max(0.0, min(1.0, float(y1)))
    clamped_x2 = max(0.0, min(1.0, float(x2)))
    clamped_y2 = max(0.0, min(1.0, float(y2)))

    if clamped_x1 >= clamped_x2 or clamped_y1 >= clamped_y2:
        raise ValueError(
            f"Invalid bounding box: ({clamped_x1}, {clamped_y1}, {clamped_x2}, {clamped_y2}) "
            f"must satisfy x1 < x2 and y1 < y2."
        )

    return (
        round(clamped_x1, 6),
        round(clamped_y1, 6),
        round(clamped_x2, 6),
        round(clamped_y2, 6),
    )
