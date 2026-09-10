"""Frame decoder: MP4 → Iterator[Frame] via OpenCV (Blueprint Section 9.1).

Converts a normalized MP4 file into Frame objects, fed through the existing
FrameSampler for PTS-based sampling at inference FPS.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterator

import cv2

from warehouse_ai.domain.models import Frame

logger = logging.getLogger(__name__)


def decode_frames(path: Path | str) -> Iterator[Frame]:
    """Decode every raw frame from an MP4 via cv2.VideoCapture.

    Yields Frame(index, timestamp_ms, bgr) in chronological order.
    timestamp_ms comes from CAP_PROP_POS_MSEC; if the codec returns 0.0
    for every frame we fall back to frame_index * 1000 / fps.

    Pass the output through FrameSampler to get PTS-sampled frames:

        frames = list(FrameSampler(target_fps=10).sample(decode_frames(path)))

    The capture is always released in a finally block.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Video file not found: {path}")

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"cv2.VideoCapture could not open: {path}")

    fps: float = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frame_index = 0
    pts_unreliable = False

    try:
        while True:
            ret, bgr = cap.read()
            if not ret:
                break

            # Primary: PTS from the demuxer
            pos_ms = cap.get(cv2.CAP_PROP_POS_MSEC)

            # Detect unreliable PTS (always 0 after the first frame)
            if frame_index == 1 and pos_ms == 0.0:
                pts_unreliable = True
                logger.debug("CAP_PROP_POS_MSEC unreliable for %s — using frame-count fallback", path.name)

            if pts_unreliable or pos_ms == 0.0 and frame_index > 0:
                timestamp_ms = int(round(frame_index * 1000.0 / fps))
            else:
                timestamp_ms = int(round(pos_ms))

            yield Frame(index=frame_index, timestamp_ms=timestamp_ms, bgr=bgr)
            frame_index += 1

    finally:
        cap.release()

    logger.debug("decode_frames: finished %d raw frames from %s", frame_index, path.name)
