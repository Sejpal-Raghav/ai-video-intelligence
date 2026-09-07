import gzip
import io
import json
from pathlib import Path
from typing import Sequence

from warehouse_ai.domain.models import TrackFrame, TrackObservation


def interpolate_tracks(
    track_frames: Sequence[TrackFrame], max_gap_ms: int = 200
) -> list[TrackFrame]:
    """Linearly interpolate missing observations when same track reappears within max_gap_ms (Section 9.1 rule 3).
    
    Interpolated observations have is_interpolated=True.
    """
    if not track_frames:
        return []

    # Map track_id -> sorted list of (frame_idx_in_list, timestamp_ms, TrackObservation)
    track_history: dict[int, list[tuple[int, int, TrackObservation]]] = {}
    for idx, tf in enumerate(track_frames):
        for obs in tf.tracks:
            track_history.setdefault(obs.track_id, []).append((idx, tf.timestamp_ms, obs))

    # Build additions per frame index: frame_idx -> list of TrackObservation
    interpolated_additions: dict[int, list[TrackObservation]] = {
        i: [] for i in range(len(track_frames))
    }

    for track_id, appearances in track_history.items():
        for a_idx in range(len(appearances) - 1):
            start_f_idx, start_t, start_obs = appearances[a_idx]
            end_f_idx, end_t, end_obs = appearances[a_idx + 1]

            gap_ms = end_t - start_t
            if 0 < gap_ms <= max_gap_ms and end_f_idx > start_f_idx + 1:
                # Interpolate intermediate frames
                for mid_f_idx in range(start_f_idx + 1, end_f_idx):
                    mid_t = track_frames[mid_f_idx].timestamp_ms
                    alpha = (mid_t - start_t) / float(gap_ms)

                    sx1, sy1, sx2, sy2 = start_obs.bbox_xyxy_norm
                    ex1, ey1, ex2, ey2 = end_obs.bbox_xyxy_norm

                    ix1 = round(sx1 + alpha * (ex1 - sx1), 6)
                    iy1 = round(sy1 + alpha * (ey1 - sy1), 6)
                    ix2 = round(sx2 + alpha * (ex2 - sx2), 6)
                    iy2 = round(sy2 + alpha * (ey2 - sy2), 6)
                    iconf = round(start_obs.confidence + alpha * (end_obs.confidence - start_obs.confidence), 6)

                    interp_obs = TrackObservation(
                        track_id=track_id,
                        class_id=start_obs.class_id,
                        confidence=iconf,
                        bbox_xyxy_norm=(ix1, iy1, ix2, iy2),
                        is_interpolated=True,
                    )
                    interpolated_additions[mid_f_idx].append(interp_obs)

    # Reconstruct frames with interpolated observations, sorted by (class_id, track_id)
    result: list[TrackFrame] = []
    for idx, tf in enumerate(track_frames):
        merged_tracks = list(tf.tracks) + interpolated_additions[idx]
        merged_tracks.sort(key=lambda o: (o.class_id, o.track_id))
        result.append(
            TrackFrame(
                schema_version=tf.schema_version,
                frame_index=tf.frame_index,
                timestamp_ms=tf.timestamp_ms,
                frame_width=tf.frame_width,
                frame_height=tf.frame_height,
                tracks=merged_tracks,
            )
        )

    return result


def serialize_canonical_track_frame(tf: TrackFrame) -> str:
    """Serialize a TrackFrame to canonical JSON with sorted keys, rounded numbers, and trailing newline."""
    sorted_tracks = sorted(tf.tracks, key=lambda o: (o.class_id, o.track_id))
    frame_dict = {
        "frame_height": tf.frame_height,
        "frame_index": tf.frame_index,
        "frame_width": tf.frame_width,
        "schema_version": tf.schema_version,
        "timestamp_ms": tf.timestamp_ms,
        "tracks": [
            {
                "bbox_xyxy_norm": [round(c, 6) for c in obs.bbox_xyxy_norm],
                "class_id": obs.class_id,
                "confidence": round(obs.confidence, 6),
                "is_interpolated": obs.is_interpolated,
                "track_id": obs.track_id,
            }
            for obs in sorted_tracks
        ],
    }
    return json.dumps(frame_dict, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"


def write_canonical_tracks(
    track_frames: Sequence[TrackFrame], out_path: Path | str
) -> None:
    """Write TrackFrames to tracks.jsonl.gz with canonical gzip mtime=0 (Section 9)."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Sort frames strictly by (timestamp_ms, frame_index)
    sorted_frames = sorted(track_frames, key=lambda f: (f.timestamp_ms, f.frame_index))

    bio = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=bio, mtime=0.0) as gz:
        for tf in sorted_frames:
            line_str = serialize_canonical_track_frame(tf)
            gz.write(line_str.encode("utf-8"))

    with open(out_path, "wb") as f:
        f.write(bio.getvalue())


def read_canonical_tracks(in_path: Path | str) -> list[TrackFrame]:
    """Read TrackFrames from canonical tracks.jsonl.gz."""
    in_path = Path(in_path)
    if not in_path.exists():
        raise FileNotFoundError(f"Track file not found: {in_path}")

    opener = gzip.open if str(in_path).endswith(".gz") else open
    frames: list[TrackFrame] = []
    with opener(in_path, "rt", encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()
            if not line_str:
                continue
            data = json.loads(line_str)
            frames.append(TrackFrame.model_validate(data))

    return frames
