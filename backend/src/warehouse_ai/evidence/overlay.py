from typing import Any
import numpy as np
from PIL import Image, ImageDraw, ImageFont


def draw_event_overlay(
    frame_image: Any,  # PIL Image or np.ndarray
    timestamp_ms: int,
    tracks: list[dict[str, Any]],  # list of dicts with track_id, class_id, bbox_xyxy_norm
    active_event_label: str | None = None,
    risk_tier_color: tuple[int, int, int] = (255, 165, 0),
) -> Any:
    """Draw bounding boxes, track IDs, timestamp, and active event badge on a frame (Section 8.3)."""
    is_numpy = isinstance(frame_image, np.ndarray)
    if is_numpy:
        pil_img = Image.fromarray(frame_image)
    else:
        pil_img = frame_image.copy()

    draw = ImageDraw.Draw(pil_img)
    w, h = pil_img.size

    # 1. Format timestamp string MM:SS.mmm
    seconds = timestamp_ms // 1000
    ms = timestamp_ms % 1000
    minutes = seconds // 60
    sec = seconds % 60
    ts_str = f"{minutes:02d}:{sec:02d}.{ms:03d}"

    # Draw timestamp box in top-left
    draw.rectangle([(10, 10), (160, 42)], fill=(0, 0, 0, 180), outline=(200, 200, 200))
    draw.text((20, 18), ts_str, fill=(255, 255, 255))

    # 2. Draw active event badge if present
    if active_event_label:
        badge_text = f"EVENT: {active_event_label}"
        draw.rectangle([(w - 300, 10), (w - 10, 46)], fill=risk_tier_color, outline=(255, 255, 255))
        draw.text((w - 285, 20), badge_text, fill=(0, 0, 0))

    # 3. Draw track bounding boxes
    colors = {
        "package": (255, 69, 0),     # Red-Orange
        "person": (30, 144, 255),    # Dodger Blue
        "pallet": (50, 205, 50),     # Lime Green
        "equipment": (255, 215, 0),  # Gold
    }

    for tr in tracks:
        cls_id = tr.get("class_id", "package")
        track_id = tr.get("track_id", 0)
        norm_box = tr.get("bbox_xyxy_norm", (0, 0, 0, 0))

        x1 = int(norm_box[0] * w)
        y1 = int(norm_box[1] * h)
        x2 = int(norm_box[2] * w)
        y2 = int(norm_box[3] * h)

        color = colors.get(cls_id, (255, 255, 255))

        # Box
        draw.rectangle([(x1, y1), (x2, y2)], outline=color, width=2)

        # Label tag
        label = f"{cls_id} #{track_id}"
        draw.rectangle([(x1, max(0, y1 - 20)), (x1 + len(label) * 8 + 8, y1)], fill=color)
        draw.text((x1 + 4, max(0, y1 - 18)), label, fill=(0, 0, 0))

    if is_numpy:
        return np.array(pil_img)
    return pil_img
