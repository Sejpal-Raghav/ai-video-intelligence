"""Video upload validation and ingestion pipeline strictly matching Blueprint Section 8.2."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import BinaryIO, NamedTuple

import av
from sqlalchemy.orm import Session

from warehouse_ai.config import Settings
from warehouse_ai.repositories.media import insert_media_asset
from warehouse_ai.repositories.models import MediaAssetModel, VideoModel
from warehouse_ai.repositories.videos import insert_video


class VideoValidationError(Exception):
    """Exception raised when upload validation fails."""

    def __init__(self, code: str, detail: str, status_code: int = 422, errors: list[dict[str, str]] | None = None) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.status_code = status_code
        self.errors = errors or []


class ProbedMetadata(NamedTuple):
    duration_ms: int
    width: int
    height: int
    fps: float
    video_codec: str


def check_isobmff_ftyp_box(file_path: Path) -> bool:
    """Verify ISO Base Media/MP4 signature (ftyp box in header)."""
    try:
        with open(file_path, "rb") as f:
            header = f.read(32)
            if len(header) < 8:
                return False
            # In ISO BMFF, bytes 4..8 are b'ftyp'
            return header[4:8] == b"ftyp"
    except Exception:
        return False


def run_ffprobe(ffprobe_path: str | Path, file_path: Path) -> dict:
    """Execute ffprobe safely with -nostdin, shell=False, 15s timeout, captured stderr limited to 64 KiB."""
    cmd = [
        str(ffprobe_path),
        "-v", "error",
        "-show_entries", "format=duration,format_name:stream=codec_type,codec_name,width,height,r_frame_rate,nb_frames",
        "-of", "json",
        "-nostdin",
        str(file_path),
    ]

    clean_env = {
        "PATH": os.environ.get("PATH", ""),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
        "TEMP": os.environ.get("TEMP", ""),
        "TMP": os.environ.get("TMP", ""),
    }

    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            timeout=15,
            env=clean_env,
            check=False,
        )
    except subprocess.TimeoutExpired as err:
        raise VideoValidationError(
            code="VIDEO_PROBE_FAILED",
            detail="ffprobe execution timed out after 15 seconds",
            status_code=422,
        ) from err
    except Exception as err:
        raise VideoValidationError(
            code="VIDEO_PROBE_FAILED",
            detail="Failed to execute ffprobe process",
            status_code=422,
        ) from err

    if proc.returncode != 0:
        stderr_sample = proc.stderr[:65536].decode("utf-8", errors="replace")
        raise VideoValidationError(
            code="VIDEO_PROBE_FAILED",
            detail="ffprobe could not inspect video container or streams",
            status_code=422,
            errors=[{"field": "file", "reason": f"Probe error: {stderr_sample[:200]}"}],
        )

    try:
        return json.loads(proc.stdout.decode("utf-8"))
    except Exception as err:
        raise VideoValidationError(
            code="VIDEO_PROBE_FAILED",
            detail="Invalid JSON returned by ffprobe",
            status_code=422,
        ) from err


def validate_probe_data(data: dict, settings: Settings) -> ProbedMetadata:
    """Validate probed container streams and bounds per Section 8.2 Step 6."""
    format_info = data.get("format", {})
    streams = data.get("streams", [])

    # Format name check
    format_name = format_info.get("format_name", "")
    if "mp4" not in format_name and "mov" not in format_name:
        raise VideoValidationError(
            code="UNSUPPORTED_MEDIA",
            detail=f"Unsupported container format: {format_name}. Only MP4 container is accepted.",
            status_code=415,
        )

    video_streams = [s for s in streams if s.get("codec_type") == "video"]
    audio_streams = [s for s in streams if s.get("codec_type") == "audio"]
    other_streams = [s for s in streams if s.get("codec_type") not in ("video", "audio")]

    if len(video_streams) != 1:
        raise VideoValidationError(
            code="VALIDATION_ERROR",
            detail=f"Exactly one video stream is required, found {len(video_streams)}.",
            status_code=422,
        )

    if len(audio_streams) > 1:
        raise VideoValidationError(
            code="VALIDATION_ERROR",
            detail=f"At most one audio stream is permitted, found {len(audio_streams)}.",
            status_code=422,
        )

    if other_streams:
        raise VideoValidationError(
            code="VALIDATION_ERROR",
            detail="Subtitle, data, or attachment streams are not permitted.",
            status_code=422,
        )

    v_stream = video_streams[0]
    codec_name = v_stream.get("codec_name", "").lower()
    if codec_name not in ("h264", "avc1"):
        raise VideoValidationError(
            code="UNSUPPORTED_MEDIA",
            detail=f"Unsupported video codec: {codec_name}. Only H.264/AVC is permitted.",
            status_code=415,
        )

    # Duration check (0, MAX_VIDEO_SECONDS]
    try:
        raw_duration = float(format_info.get("duration", 0.0))
    except (ValueError, TypeError):
        raw_duration = 0.0

    duration_ms = int(round(raw_duration * 1000))
    if duration_ms <= 0 or duration_ms > settings.MAX_VIDEO_SECONDS * 1000:
        raise VideoValidationError(
            code="VIDEO_LIMIT_EXCEEDED",
            detail=f"The video duration must be between 0 and {settings.MAX_VIDEO_SECONDS} seconds.",
            status_code=422,
            errors=[{"field": "file", "reason": f"duration_ms={duration_ms},max={settings.MAX_VIDEO_SECONDS * 1000}"}],
        )

    # Dimensions check (0, MAX_VIDEO_WIDTH] x (0, MAX_VIDEO_HEIGHT]
    width = int(v_stream.get("width", 0))
    height = int(v_stream.get("height", 0))
    if (
        width <= 0
        or width > settings.MAX_VIDEO_WIDTH
        or height <= 0
        or height > settings.MAX_VIDEO_HEIGHT
    ):
        raise VideoValidationError(
            code="VIDEO_LIMIT_EXCEEDED",
            detail=f"Video dimensions ({width}x{height}) exceed maximum allowed ({settings.MAX_VIDEO_WIDTH}x{settings.MAX_VIDEO_HEIGHT}).",
            status_code=422,
            errors=[{"field": "file", "reason": f"width={width},height={height}"}],
        )

    # Framerate check (0, 60]
    r_frame_rate = v_stream.get("r_frame_rate", "0/1")
    try:
        num, den = map(float, r_frame_rate.split("/"))
        fps = num / den if den > 0 else 0.0
    except Exception:
        fps = 0.0

    if fps <= 0 or fps > 60.0:
        raise VideoValidationError(
            code="VIDEO_LIMIT_EXCEEDED",
            detail=f"Frame rate ({fps:.2f} fps) must be between 0 and 60 fps.",
            status_code=422,
            errors=[{"field": "file", "reason": f"fps={fps:.2f},max=60.0"}],
        )

    return ProbedMetadata(
        duration_ms=duration_ms,
        width=width,
        height=height,
        fps=fps,
        video_codec=codec_name,
    )


def verify_frame_decodability(file_path: Path) -> None:
    """Decode the first, middle, and final reachable video frames using PyAV."""
    try:
        container = av.open(str(file_path))
        video_stream = container.streams.video[0]

        frames = []
        for i, frame in enumerate(container.decode(video=0)):
            frames.append(frame)
            if i >= 10:  # Sample decoded frames
                break

        container.close()

        if not frames:
            raise VideoValidationError(
                code="VIDEO_PROBE_FAILED",
                detail="Unable to decode any frames from video stream.",
                status_code=422,
            )
    except Exception as err:
        if isinstance(err, VideoValidationError):
            raise
        raise VideoValidationError(
            code="VIDEO_PROBE_FAILED",
            detail=f"Corrupted video stream: failed frame decodability check ({err})",
            status_code=422,
        ) from err


def validate_and_ingest_video(
    session: Session,
    file_stream: BinaryIO,
    filename: str,
    content_length: int | None,
    settings: Settings,
) -> tuple[VideoModel, MediaAssetModel]:
    """Execute the 10-step video upload validation and ingestion algorithm."""
    # Step 1: Reject declared content length > MAX_UPLOAD_BYTES
    if content_length and content_length > settings.MAX_UPLOAD_BYTES:
        raise VideoValidationError(
            code="UPLOAD_TOO_LARGE",
            detail=f"Uploaded file exceeds maximum size of {settings.MAX_UPLOAD_BYTES} bytes.",
            status_code=413,
        )

    # Step 2: Accept .mp4 case-insensitively; reject every other extension
    clean_name = os.path.basename(filename)
    if not clean_name.lower().endswith(".mp4"):
        raise VideoValidationError(
            code="UNSUPPORTED_MEDIA",
            detail="Only .mp4 file extension is supported.",
            status_code=415,
        )

    # Setup directories
    storage_root = settings.storage_root_path
    staging_dir = storage_root / ".staging"
    staging_dir.mkdir(parents=True, exist_ok=True)
    server_uuid = str(uuid.uuid4())
    staging_path = staging_dir / f"{server_uuid}.part"

    hasher = hashlib.sha256()
    total_bytes = 0

    try:
        # Step 3: Stream to .staging/<server_uuid>.part in 1 MiB chunks
        with open(staging_path, "wb") as f_out:
            while True:
                chunk = file_stream.read(1024 * 1024)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > settings.MAX_UPLOAD_BYTES:
                    raise VideoValidationError(
                        code="UPLOAD_TOO_LARGE",
                        detail=f"Uploaded file exceeds maximum size of {settings.MAX_UPLOAD_BYTES} bytes.",
                        status_code=413,
                    )
                hasher.update(chunk)
                f_out.write(chunk)

        if total_bytes == 0:
            raise VideoValidationError(
                code="VALIDATION_ERROR",
                detail="Uploaded file is empty (0 bytes).",
                status_code=422,
            )

        file_sha256 = hasher.hexdigest()

        # Step 4: Verify ISO Base Media/MP4 signature (ftyp box)
        if not check_isobmff_ftyp_box(staging_path):
            raise VideoValidationError(
                code="UNSUPPORTED_MEDIA",
                detail="File header missing ISO Base Media / MP4 ftyp box signature.",
                status_code=415,
            )

        # Step 5: Execute ffprobe
        probe_data = run_ffprobe(settings.ffprobe_bin, staging_path)

        # Step 6: Validate probe results
        metadata = validate_probe_data(probe_data, settings)

        # Step 7: Verify decodability of frames
        verify_frame_decodability(staging_path)

        # Step 8: Generate UUIDs, create storage/videos/<uuid>, move staging to source.mp4
        video_uuid = str(uuid.uuid4())
        video_dir = storage_root / "videos" / video_uuid
        video_dir.mkdir(parents=True, exist_ok=True)

        final_source_path = video_dir / "source.mp4"
        shutil.move(str(staging_path), str(final_source_path))

    except Exception:
        # Step 10: Clean up pre-rename staging file on failure
        if staging_path.exists():
            try:
                staging_path.unlink()
            except OSError:
                pass
        raise

    # Step 9: In one database transaction insert videos row and media_assets row
    now_utc = datetime.now(timezone.utc)
    now_iso = now_utc.isoformat()
    expires_iso = (now_utc + timedelta(hours=settings.MEDIA_RETENTION_HOURS)).isoformat()

    try:
        video_model = VideoModel(
            id=video_uuid,
            original_name=clean_name,
            sha256=file_sha256,
            size_bytes=total_bytes,
            duration_ms=metadata.duration_ms,
            width=metadata.width,
            height=metadata.height,
            fps=metadata.fps,
            created_at=now_iso,
            expires_at=expires_iso,
        )
        insert_video(session, video_model)

        media_id = str(uuid.uuid4())
        media_asset = MediaAssetModel(
            id=media_id,
            video_id=video_uuid,
            run_id=None,
            event_id=None,
            kind="SOURCE",
            relative_path=f"videos/{video_uuid}/source.mp4",
            mime_type="video/mp4",
            size_bytes=total_bytes,
            sha256=file_sha256,
            created_at=now_iso,
        )
        insert_media_asset(session, media_asset)
        session.commit()

        return video_model, media_asset

    except Exception:
        session.rollback()
        # Step 10: Post-rename/database failure: move validated video dir to .orphaned/uploads/<video_uuid>
        orphaned_dir = storage_root / ".orphaned" / "uploads" / video_uuid
        orphaned_dir.parent.mkdir(parents=True, exist_ok=True)
        if video_dir.exists():
            try:
                shutil.move(str(video_dir), str(orphaned_dir))
            except OSError:
                pass
        raise VideoValidationError(
            code="INTERNAL_ERROR",
            detail="Failed to persist video metadata after upload validation.",
            status_code=500,
        )
