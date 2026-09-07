"""Evidence clip clipping, thumbnail extraction, and trace writing matching Blueprint Section 8.3 & 13."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, NamedTuple


class ClipResult(NamedTuple):
    clip_path: Path
    clip_sha256: str
    clip_size_bytes: int
    thumb_path: Path
    thumb_sha256: str
    thumb_size_bytes: int
    trace_path: Path
    trace_sha256: str
    trace_size_bytes: int


def compute_file_sha256(path: Path) -> tuple[str, int]:
    """Compute SHA-256 and byte size of a file."""
    hasher = hashlib.sha256()
    size = 0
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            hasher.update(chunk)
            size += len(chunk)
    return hasher.hexdigest(), size


def create_event_evidence(
    ffmpeg_path: str | Path,
    source_video_path: Path,
    output_dir: Path,
    event_type: str,
    start_ms: int,
    end_ms: int,
    video_duration_ms: int,
    decision_trace: dict[str, Any],
    impact_timestamp_ms: int | None = None,
    timeout_seconds: int = 60,
) -> ClipResult:
    """Generate clip.mp4, thumbnail.jpg, and trace.json for an event.

    Clip interval: [max(0, start_ms - 1500), min(duration_ms, end_ms + 1500)]
    Thumbnail: impact timestamp if provided, else midpoint frame.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    clip_start_ms = max(0, start_ms - 1500)
    clip_end_ms = min(video_duration_ms, end_ms + 1500)
    if clip_end_ms <= clip_start_ms:
        clip_end_ms = clip_start_ms + 1000

    start_sec = clip_start_ms / 1000.0
    duration_sec = (clip_end_ms - clip_start_ms) / 1000.0

    # Determine thumbnail timestamp
    if impact_timestamp_ms is not None:
        thumb_sec = max(0.0, min(video_duration_ms / 1000.0, impact_timestamp_ms / 1000.0))
    else:
        thumb_sec = (start_ms + end_ms) / 2000.0

    clip_path = output_dir / "clip.mp4"
    thumb_path = output_dir / "thumbnail.jpg"
    trace_path = output_dir / "trace.json"

    clean_env = {
        "PATH": os.environ.get("PATH", ""),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
        "TEMP": os.environ.get("TEMP", ""),
        "TMP": os.environ.get("TMP", ""),
    }

    # 1. Generate clip.mp4 with FFmpeg
    clip_cmd = [
        str(ffmpeg_path),
        "-y",
        "-nostdin",
        "-ss", f"{start_sec:.3f}",
        "-t", f"{duration_sec:.3f}",
        "-i", str(source_video_path),
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "22",
        "-pix_fmt", "yuv420p",
        "-an",
        "-movflags", "+faststart",
        str(clip_path),
    ]

    subprocess.run(
        clip_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        timeout=timeout_seconds,
        env=clean_env,
        check=False,
    )

    # 2. Extract thumbnail.jpg
    thumb_cmd = [
        str(ffmpeg_path),
        "-y",
        "-nostdin",
        "-ss", f"{thumb_sec:.3f}",
        "-i", str(source_video_path),
        "-vframes", "1",
        "-q:v", "2",
        str(thumb_path),
    ]

    subprocess.run(
        thumb_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        timeout=timeout_seconds,
        env=clean_env,
        check=False,
    )

    # 3. Write trace.json
    trace_json_str = json.dumps(decision_trace, indent=2, sort_keys=True)
    with open(trace_path, "w", encoding="utf-8") as f:
        f.write(trace_json_str)
        f.flush()
        os.fsync(f.fileno())

    # Calculate hashes and sizes
    clip_sha256, clip_size = compute_file_sha256(clip_path) if clip_path.exists() else ("", 0)
    thumb_sha256, thumb_size = compute_file_sha256(thumb_path) if thumb_path.exists() else ("", 0)
    trace_sha256, trace_size = compute_file_sha256(trace_path)

    return ClipResult(
        clip_path=clip_path,
        clip_sha256=clip_sha256,
        clip_size_bytes=clip_size,
        thumb_path=thumb_path,
        thumb_sha256=thumb_sha256,
        thumb_size_bytes=thumb_size,
        trace_path=trace_path,
        trace_sha256=trace_sha256,
        trace_size_bytes=trace_size,
    )
