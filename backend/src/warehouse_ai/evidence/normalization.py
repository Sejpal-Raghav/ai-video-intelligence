"""Video normalization using FFmpeg matching Blueprint Section 8.3."""

from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path
from typing import NamedTuple


class NormalizedMediaResult(NamedTuple):
    path: Path
    sha256: str
    size_bytes: int
    duration_ms: int
    fps: float
    width: int
    height: int


def normalize_video(
    ffmpeg_path: str | Path,
    source_path: Path,
    output_path: Path,
    source_fps: float,
    timeout_seconds: int = 180,
) -> NormalizedMediaResult:
    """Normalize input video to H.264 MP4, yuv420p, min(fps, 25), start PTS 0, audio removed, +faststart."""
    target_fps = min(source_fps, 25.0) if source_fps > 0 else 25.0
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # FFmpeg scale filter: max long edge 1920, even dimensions
    # scale='if(gte(iw,ih),min(1920,iw),-2)':'if(gte(iw,ih),-2,min(1920,ih))'
    scale_filter = "scale=w='if(gte(iw,ih),min(1920,iw),-2)':h='if(gte(iw,ih),-2,min(1920,ih))'"
    vf = f"setpts=PTS-STARTPTS,{scale_filter},format=yuv420p"

    cmd = [
        str(ffmpeg_path),
        "-y",
        "-nostdin",
        "-i", str(source_path),
        "-vf", vf,
        "-r", f"{target_fps:.2f}",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "22",
        "-an",
        "-movflags", "+faststart",
        str(output_path),
    ]

    clean_env = {
        "PATH": os.environ.get("PATH", ""),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
        "TEMP": os.environ.get("TEMP", ""),
        "TMP": os.environ.get("TMP", ""),
    }

    proc = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
        timeout=timeout_seconds,
        env=clean_env,
        check=False,
    )

    if proc.returncode != 0:
        stderr_msg = proc.stderr[:65536].decode("utf-8", errors="replace")
        raise RuntimeError(f"FFmpeg normalization failed: {stderr_msg[:300]}")

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError("Normalized video file was not generated or is empty.")

    # Compute SHA-256 and size
    hasher = hashlib.sha256()
    size_bytes = 0
    with open(output_path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            hasher.update(chunk)
            size_bytes += len(chunk)
    file_sha256 = hasher.hexdigest()

    return NormalizedMediaResult(
        path=output_path,
        sha256=file_sha256,
        size_bytes=size_bytes,
        duration_ms=0,
        fps=target_fps,
        width=0,
        height=0,
    )
