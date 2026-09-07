import gzip
import json
from pathlib import Path
from typing import Iterable, Sequence

from warehouse_ai.domain.models import Frame, TrackFrame, TrackedDetection


class ReplayAdapter:
    """Deterministic adapter yielding precomputed tracks from tracks.jsonl.gz (Section 5.3 & 13.1)."""

    backend_name: str = "replay"

    def __init__(self, tracks_path: Path | str, model_sha256: str = "replay") -> None:
        self.tracks_path = Path(tracks_path)
        self.model_sha256 = model_sha256
        self._frames_by_timestamp: dict[int, list[TrackedDetection]] = {}
        self._load_tracks()

    def _load_tracks(self) -> None:
        if not self.tracks_path.exists():
            raise FileNotFoundError(f"Replay track artifact not found: {self.tracks_path}")

        opener = gzip.open if str(self.tracks_path).endswith(".gz") else open
        with opener(self.tracks_path, "rt", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if not line_str:
                    continue
                data = json.loads(line_str)
                track_frame = TrackFrame.model_validate(data)
                detections = [
                    TrackedDetection(
                        class_id=obs.class_id,
                        confidence=obs.confidence,
                        bbox_xyxy_norm=obs.bbox_xyxy_norm,
                        track_id=obs.track_id,
                        is_interpolated=obs.is_interpolated,
                    )
                    for obs in track_frame.tracks
                ]
                self._frames_by_timestamp[track_frame.timestamp_ms] = detections

    def process(self, frames: Iterable[Frame]) -> Iterable[Sequence[TrackedDetection]]:
        """Yield exactly one detection sequence for every input frame in order."""
        for frame in frames:
            # Match by exact timestamp_ms, or return empty sequence if no tracks for this frame
            yield self._frames_by_timestamp.get(frame.timestamp_ms, [])
