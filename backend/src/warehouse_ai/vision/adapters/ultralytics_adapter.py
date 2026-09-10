import hashlib
from pathlib import Path
from typing import Any, Iterable, Sequence

from warehouse_ai.domain.models import Frame, TrackedDetection


class UltralyticsAdapter:
    """Ultralytics YOLO + ByteTrack adapter isolated behind DetectorTracker protocol (Section 5.3).

    The class map is injectable so the factory can pass a COCO warehouse
    allowlist.  Any COCO class id *not* present in the map is silently
    dropped — this prevents cars/chairs/people-adjacent objects from being
    mislabelled as ``package``.
    """

    backend_name: str = "ultralytics"

    # Default class map for a purpose-trained 4-class warehouse model.
    # When using stock COCO weights the factory overrides this with the
    # COCO warehouse allowlist (see vision/factory.py).
    _DEFAULT_CLASS_MAP: dict[int, str] = {
        0: "person",
        1: "package",
        2: "pallet",
        3: "equipment",
    }

    def __init__(
        self,
        model_path: Path | str,
        tracker_config_path: Path | str,
        device: str = "cpu",
        confidence_thresholds: dict[str, float] | None = None,
        class_map: dict[int, str] | None = None,
    ) -> None:
        self.model_path = Path(model_path)
        self.tracker_config_path = Path(tracker_config_path)
        self.device = device
        self.confidence_thresholds = confidence_thresholds or {
            "person": 0.15,
            "package": 0.10,
            "pallet": 0.15,
            "equipment": 0.15,
        }
        # Injected class map takes precedence; fall back to default 4-class map.
        self._class_map: dict[int, str] = class_map if class_map is not None else dict(self._DEFAULT_CLASS_MAP)
        self.model_sha256 = self._compute_model_hash()
        self._model: Any = None

    def _compute_model_hash(self) -> str:
        if not self.model_path.exists():
            return "0000000000000000000000000000000000000000000000000000000000000000"
        hasher = hashlib.sha256()
        with open(self.model_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _ensure_model(self) -> Any:
        if self._model is None:
            try:
                from ultralytics import YOLO  # type: ignore[import-untyped]
                self._model = YOLO(str(self.model_path))
            except ImportError as e:
                raise RuntimeError(
                    "Ultralytics is not installed. To use UltralyticsAdapter, install ultralytics."
                ) from e
        return self._model

    def process(self, frames: Iterable[Frame]) -> Iterable[Sequence[TrackedDetection]]:
        """Run tracking on input frames in order and yield TrackedDetection per frame."""
        model = self._ensure_model()

        for frame in frames:
            # Run tracker with persistent state
            results = model.track(
                source=frame.bgr,
                persist=True,
                tracker=str(self.tracker_config_path),
                device=self.device,
                verbose=False,
            )

            detections: list[TrackedDetection] = []
            if not results or len(results) == 0:
                yield detections
                continue

            res = results[0]
            if res.boxes is None:
                yield detections
                continue

            orig_h, orig_w = res.orig_shape

            for box in res.boxes:
                # Track ID
                if box.id is None:
                    continue
                track_id = int(box.id.item())

                cls_idx = int(box.cls.item())

                # STRICT allowlist: drop any class id not in the map.
                # This prevents unlabelled COCO classes from becoming spurious
                # "package" detections.
                if cls_idx not in self._class_map:
                    continue
                class_id = self._class_map[cls_idx]

                conf = float(box.conf.item())
                min_conf = self.confidence_thresholds.get(class_id, 0.10)
                if conf < min_conf:
                    continue

                # Normalized coordinates xyxy clamped to [0, 1]
                xyxy = box.xyxy[0].tolist()
                x1 = max(0.0, min(1.0, xyxy[0] / orig_w))
                y1 = max(0.0, min(1.0, xyxy[1] / orig_h))
                x2 = max(0.0, min(1.0, xyxy[2] / orig_w))
                y2 = max(0.0, min(1.0, xyxy[3] / orig_h))

                if x1 >= x2 or y1 >= y2:
                    continue

                detections.append(
                    TrackedDetection(
                        class_id=class_id,
                        confidence=round(conf, 6),
                        bbox_xyxy_norm=(round(x1, 6), round(y1, 6), round(x2, 6), round(y2, 6)),
                        track_id=track_id,
                        is_interpolated=False,
                    )
                )

            yield detections
