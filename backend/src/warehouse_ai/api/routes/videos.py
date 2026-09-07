"""Video upload, retrieval, and cascade deletion endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Response, UploadFile, status
from sqlalchemy.orm import Session

from warehouse_ai.api.dependencies import get_app_settings, get_db_session, get_storage_path
from warehouse_ai.api.errors import ProblemError
from warehouse_ai.api.schemas import VideoResponse
from warehouse_ai.config import Settings
from warehouse_ai.repositories.videos import get_video
from warehouse_ai.services.ingest import VideoValidationError, validate_and_ingest_video
from warehouse_ai.services.retention import VideoActiveConflictError, delete_video_with_quarantine

router = APIRouter(prefix="/api/v1/videos", tags=["videos"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=VideoResponse)
def upload_video(
    file: UploadFile,
    content_length: int | None = Header(default=None),
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> VideoResponse:
    """Validate and ingest uploaded MP4 video according to Blueprint Section 8.2."""
    if not file.filename:
        raise ProblemError(
            status_code=400,
            code="MALFORMED_REQUEST",
            title="Missing filename",
            detail="Uploaded file must have a valid filename.",
        )

    try:
        video_model, _ = validate_and_ingest_video(
            session=session,
            file_stream=file.file,
            filename=file.filename,
            content_length=content_length,
            settings=settings,
        )
        return VideoResponse(
            id=video_model.id,
            original_name=video_model.original_name,
            sha256=video_model.sha256,
            size_bytes=video_model.size_bytes,
            duration_ms=video_model.duration_ms,
            width=video_model.width,
            height=video_model.height,
            fps=video_model.fps,
            created_at=video_model.created_at,
            expires_at=video_model.expires_at,
        )
    except VideoValidationError as err:
        raise ProblemError(
            status_code=err.status_code,
            code=err.code,
            title="Video validation failed",
            detail=err.detail,
            errors=err.errors,
        ) from err


@router.get("/{video_id}", response_model=VideoResponse)
def get_video_by_id(
    video_id: str,
    session: Session = Depends(get_db_session),
) -> VideoResponse:
    """Retrieve video metadata by ID."""
    video = get_video(session, video_id)
    if not video:
        raise ProblemError(
            status_code=404,
            code="VIDEO_NOT_FOUND",
            title="Video not found",
            detail=f"Video with ID {video_id} was not found.",
        )

    return VideoResponse(
        id=video.id,
        original_name=video.original_name,
        sha256=video.sha256,
        size_bytes=video.size_bytes,
        duration_ms=video.duration_ms,
        width=video.width,
        height=video.height,
        fps=video.fps,
        created_at=video.created_at,
        expires_at=video.expires_at,
    )


@router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_video_by_id(
    video_id: str,
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> Response:
    """Cascade delete video and all related runs, assets, and storage files."""
    video = get_video(session, video_id)
    if not video:
        raise ProblemError(
            status_code=404,
            code="VIDEO_NOT_FOUND",
            title="Video not found",
            detail=f"Video with ID {video_id} was not found.",
        )

    try:
        delete_video_with_quarantine(session, video_id, settings.storage_root_path)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except VideoActiveConflictError as err:
        raise ProblemError(
            status_code=409,
            code="RUN_IN_PROGRESS",
            title="Cannot delete video with active runs",
            detail=str(err),
        ) from err
