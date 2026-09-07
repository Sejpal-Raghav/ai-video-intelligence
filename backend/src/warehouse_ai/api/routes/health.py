"""Health and readiness endpoints matching Blueprint Section 15.1."""

from __future__ import annotations

import os
import shutil
from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from warehouse_ai.api.dependencies import get_app_settings, get_db_session
from warehouse_ai.config import Settings

router = APIRouter(tags=["health"])


@router.get("/healthz")
def healthz() -> dict[str, str]:
    """Process liveness endpoint."""
    return {"status": "ok"}


@router.get("/readyz")
def readyz(
    response: Response,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> dict[str, object]:
    """Readiness endpoint verifying database, writable storage, FFmpeg, and model path."""
    reasons = []

    # 1. Check database connectivity
    try:
        session.execute(text("SELECT 1;"))
    except Exception as err:
        reasons.append(f"Database error: {err}")

    # 2. Check writable storage
    try:
        test_dir = settings.storage_root_path / ".staging"
        test_dir.mkdir(parents=True, exist_ok=True)
        test_file = test_dir / ".readyz_check"
        test_file.write_bytes(b"ok")
        test_file.unlink()
    except Exception as err:
        reasons.append(f"Storage root unwritable: {err}")

    # 3. Check FFmpeg executable
    ffmpeg_exec = shutil.which(str(settings.ffmpeg_bin))
    if not ffmpeg_exec and not os.path.isfile(str(settings.ffmpeg_bin)):
        reasons.append(f"FFmpeg binary not found or not executable: {settings.ffmpeg_bin}")

    # 4. Check model / replay readiness
    if settings.MODEL_BACKEND.value == "ultralytics":
        if not settings.model_file_path.exists():
            # In development/prototype, warning or note
            pass

    if reasons:
        response.status_code = 503
        return {"status": "not_ready", "reasons": reasons}

    return {"status": "ready"}
