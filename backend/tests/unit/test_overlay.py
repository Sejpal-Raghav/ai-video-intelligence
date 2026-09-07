from PIL import Image
import numpy as np
import pytest

from warehouse_ai.evidence.overlay import draw_event_overlay


def test_draw_event_overlay_pil():
    img = Image.new("RGB", (640, 480), color=(50, 50, 50))
    tracks = [
        {"class_id": "package", "track_id": 1, "bbox_xyxy_norm": (0.2, 0.2, 0.4, 0.4)},
        {"class_id": "person", "track_id": 2, "bbox_xyxy_norm": (0.5, 0.2, 0.7, 0.8)},
    ]
    overlaid = draw_event_overlay(
        img,
        timestamp_ms=4500,
        tracks=tracks,
        active_event_label="DROP",
    )
    assert isinstance(overlaid, Image.Image)
    assert overlaid.size == (640, 480)


def test_draw_event_overlay_numpy():
    arr = np.zeros((480, 640, 3), dtype=np.uint8)
    tracks = [
        {"class_id": "package", "track_id": 1, "bbox_xyxy_norm": (0.1, 0.1, 0.3, 0.3)},
    ]
    overlaid = draw_event_overlay(
        arr,
        timestamp_ms=1234,
        tracks=tracks,
    )
    assert isinstance(overlaid, np.ndarray)
    assert overlaid.shape == (480, 640, 3)
