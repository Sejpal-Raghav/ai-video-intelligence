import hashlib
from pathlib import Path
from typing import Any, Iterable, Sequence

from warehouse_ai.domain.models import Frame, TrackedDetection


class UltralyticsAdapter:
    """Ultralytics YOLO + ByteTrack adapter isolated behind DetectorTracker protocol (Section 5.3)."""

    backend_name: str = "ultralytics"

    def __init__(
        self,
        model_path: Path | str,
        tracker_config_path: Path | str,
        device: str = "cpu",
        confidence_thresholds: dict[str, float] | None = None,
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
        self.model_sha256 = self._compute_model_hash()
        self._model: Any = None
        self._class_map = {0: "person", 1: "package", 2: "pallet", 3: "equipment"}

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
                class_id = self._class_map.get(cls_idx, "package")

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
