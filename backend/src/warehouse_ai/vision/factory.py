"""Detector-tracker factory: constructs the right adapter from settings (Blueprint Section 5.3)."""

from __future__ import annotations

import logging
from pathlib import Path

from warehouse_ai.config import ModelBackend, Settings
from warehouse_ai.vision.adapters.base import DetectorTracker

logger = logging.getLogger(__name__)

# Repository root relative path for the tracker config
# factory.py is at: backend/src/warehouse_ai/vision/factory.py
# .parent × 5 = repo root
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent
_TRACKER_CONFIG = _REPO_ROOT / "config" / "tracker.bytetrack.v1.yaml"

# Model auto-download name when the weights file is absent
_YOLO_DEFAULT_MODEL = "yolo11n.pt"


def _resolve_auto_device() -> str:
    """Resolve MODEL_DEVICE=auto to 'cuda:0' if a CUDA GPU is available, else 'cpu'.

    torch is already a dependency of ultralytics, so this adds no new
    dependency. Falls back to 'cpu' if torch/CUDA cannot be queried for any
    reason (e.g. a CPU-only torch build) rather than raising.
    """
    try:
        import torch  # type: ignore[import-untyped]

        if torch.cuda.is_available():
            return "cuda:0"
    except Exception:
        logger.debug("CUDA availability check failed; defaulting to cpu", exc_info=True)
    return "cpu"


def build_detector_tracker(settings: Settings) -> DetectorTracker:
    """Construct and return a DetectorTracker matching settings.MODEL_BACKEND.

    Branches:
      - ``ultralytics``: UltralyticsAdapter with COCO warehouse class map.
        If model_file_path does not exist, falls back to auto-downloading
        yolo11n.pt (Ultralytics caches it to ~/.cache/ultralytics/).
      - ``replay``:      ReplayAdapter loading a pre-recorded tracks.jsonl.gz.
        The tracks path must be set via REPLAY_TRACKS_PATH env var or
        passed explicitly; raises if not found.

    Raises:
        ValueError: if MODEL_BACKEND is not a recognised value.
        FileNotFoundError: if replay mode and no tracks file is found.
    """
    if settings.MODEL_BACKEND == ModelBackend.ULTRALYTICS:
        from warehouse_ai.vision.adapters.ultralytics_adapter import UltralyticsAdapter

        model_path = settings.model_file_path
        if not model_path.exists():
            # Fall back to auto-download of the nano model
            logger.warning(
                "Model weights not found at %s — using auto-downloaded %s",
                model_path,
                _YOLO_DEFAULT_MODEL,
            )
            model_path = Path(_YOLO_DEFAULT_MODEL)  # ultralytics resolves from cache

        device = settings.MODEL_DEVICE.value
        if device == "auto":
            device = _resolve_auto_device()

        tracker_config = _TRACKER_CONFIG
        if not tracker_config.exists():
            raise FileNotFoundError(f"Tracker config not found: {tracker_config}")

        logger.info(
            "Building UltralyticsAdapter: model=%s device=%s tracker=%s",
            model_path,
            device,
            tracker_config,
        )

        # COCO warehouse class map, validated against all 7 real videos in
        # data/video/ by running the actual production adapter loop (decode ->
        # FrameSampler(10fps) -> per-frame model.track(persist=True)) and
        # measuring per-track-id continuity, not just raw per-frame counts.
        #
        # The original map (24/26/28/58/59 only) produced ZERO package tracks
        # with a >=500ms span on any of the 7 videos (500ms/5 samples-at-10fps
        # is the minimum most rule engines need). Classes 58 (potted plant) and
        # 59 (bed) individually never fired at all in that map's own spike
        # output — they were included without verification. This expanded map
        # gets a qualifying (>=500ms) package-track span on 3/7 real videos:
        #   - Throwing Mattresses.mp4:                     2500ms span, 7 tracks, 51 detections
        #   - Throwing seating cartons, using strap...mp4: 1400ms span, 3 tracks, 13 detections
        #   - Rolling and dropping carton.mp4:               700ms span, 5 tracks, 15 detections
        # The remaining 4 videos (Dock level dragging cupboard, KD packets
        # dragged, Rolling and dragging on wet floor, Stepping on cartons) still
        # get weak-to-zero package detections — cupboards/KD-wrapped packets
        # don't map cleanly onto any stock COCO class. That is a genuine limit
        # of a pretrained general-purpose detector used as a package proxy, not
        # a bug; a purpose-trained detector (per docs/model_card.md) would be
        # needed to close that gap. track_buffer was also tested at 5 vs 40 and
        # made negligible difference (the bottleneck is raw detection recall,
        # not occlusion-bridging), so the tracker config is left unchanged.
        #   0  → person
        #  24  → package  (backpack)
        #  26  → package  (handbag)
        #  28  → package  (suitcase — most reliable carton proxy in COCO)
        #  56  → package  (chair — proxy for stacked crates/cartons)
        #  57  → package  (couch — proxy for large soft-sided items)
        #  59  → package  (bed — proxy for mattresses; validated, see above)
        #  60  → package  (dining table — proxy for flat large items)
        #  62  → package  (tv — proxy for boxed electronics)
        #  63  → package  (laptop — proxy for small boxed goods)
        #  67  → package  (cell phone — proxy for small handled items)
        #  73  → package  (book — proxy for stacked small cartons)
        coco_class_map: dict[int, str] = {
            0: "person",
            24: "package",
            26: "package",
            28: "package",
            56: "package",
            57: "package",
            59: "package",
            60: "package",
            62: "package",
            63: "package",
            67: "package",
            73: "package",
        }

        return UltralyticsAdapter(
            model_path=model_path,
            tracker_config_path=tracker_config,
            device=device,
            class_map=coco_class_map,
            # package confidence matches the validated spike (0.05); COCO
            # proxy classes for "package" are rare and low-confidence on
            # warehouse footage, so the 0.10 purpose-trained-model default
            # would drop detections the spike showed are usable.
            confidence_thresholds={
                "person": 0.15,
                "package": 0.05,
                "pallet": 0.15,
                "equipment": 0.15,
            },
        )

    elif settings.MODEL_BACKEND == ModelBackend.REPLAY:
        from warehouse_ai.vision.adapters.replay_adapter import ReplayAdapter
        import os

        tracks_path_str = os.environ.get("REPLAY_TRACKS_PATH", "")
        if not tracks_path_str:
            raise FileNotFoundError(
                "MODEL_BACKEND=replay requires REPLAY_TRACKS_PATH env var pointing to tracks.jsonl.gz"
            )
        tracks_path = Path(tracks_path_str)
        if not tracks_path.exists():
            raise FileNotFoundError(f"Replay tracks file not found: {tracks_path}")

        logger.info("Building ReplayAdapter: tracks=%s", tracks_path)
        return ReplayAdapter(tracks_path=tracks_path)

    else:
        raise ValueError(
            f"Unknown MODEL_BACKEND: {settings.MODEL_BACKEND!r}. "
            "Valid values: 'ultralytics', 'replay'."
        )
