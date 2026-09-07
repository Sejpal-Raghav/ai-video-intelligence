"""Media streaming endpoint supporting RFC 7233 byte ranges matching Blueprint Section 15.4."""

from __future__ import annotations

import os
from collections.abc import Generator
from fastapi import APIRouter, Depends, Header, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from warehouse_ai.api.dependencies import get_app_settings, get_db_session
from warehouse_ai.api.errors import ProblemError
from warehouse_ai.config import Settings
from warehouse_ai.repositories.media import (
    MediaNotFoundError,
    PathTraversalError,
    get_media_asset,
    resolve_media_path,
)

router = APIRouter(prefix="/api/v1/media", tags=["media"])


def parse_byte_range(
    range_header: str | None, total_size: int
) -> tuple[int, int] | None:
    """Parse HTTP Range header supporting single byte ranges.

    Supports:
    - 'bytes=start-end'
    - 'bytes=start-'
    - 'bytes=-suffix_length'
    Rejects:
    - Multiple ranges (contains ',')
    - Invalid or unsatisfiable ranges (returns None or raises ValueError)
    """
    if not range_header:
        return None

    if not range_header.startswith("bytes="):
        raise ValueError("Invalid range unit")

    range_spec = range_header[6:].strip()
    if "," in range_spec:
        # Multiple ranges are not supported per Section 15.4
        raise ValueError("Multiple ranges are not supported")

    parts = range_spec.split("-", 1)
    if len(parts) != 2:
        raise ValueError("Malformed range")

    start_str, end_str = parts[0].strip(), parts[1].strip()

    if not start_str and not end_str:
        raise ValueError("Empty range bounds")

    if not start_str:
        # Suffix range: bytes=-suffix_length
        suffix = int(end_str)
        if suffix <= 0:
            raise ValueError("Suffix must be positive")
        start = max(0, total_size - suffix)
        end = total_size - 1
    elif not end_str:
        # Prefix range: bytes=start-
        start = int(start_str)
        end = total_size - 1
    else:
        # Bounded range: bytes=start-end
        start = int(start_str)
        end = int(end_str)

    if start > end or start >= total_size or start < 0:
        return None  # Unsatisfiable

    end = min(end, total_size - 1)
    return start, end


def stream_file_chunk(
    path: str, start: int, length: int, chunk_size: int = 65536
) -> Generator[bytes, None, None]:
    """Yield file bytes for the specified range."""
    with open(path, "rb") as f:
        f.seek(start)
        remaining = length
        while remaining > 0:
            to_read = min(remaining, chunk_size)
            chunk = f.read(to_read)
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


@router.get("/{media_id}")
@router.head("/{media_id}")
def stream_media(
    media_id: str,
    request: Request,
    range: str | None = Header(default=None),
    session: Session = Depends(get_db_session),
    settings: Settings = Depends(get_app_settings),
) -> Response:
    """Stream authorized media asset supporting RFC 7233 byte ranges."""
    asset = get_media_asset(session, media_id)
    if not asset:
        raise ProblemError(
            status_code=404,
            code="MEDIA_NOT_FOUND",
            title="Media not found",
            detail=f"Media asset with ID {media_id} was not found.",
        )

    try:
        file_path = resolve_media_path(asset.relative_path, settings.storage_root_path)
    except (PathTraversalError, MediaNotFoundError) as err:
        raise ProblemError(
            status_code=404,
            code="MEDIA_NOT_FOUND",
            title="Media file not found",
            detail=str(err),
        ) from err

    total_size = asset.size_bytes
    etag = f'"{asset.sha256}"'
    base_headers = {
        "Accept-Ranges": "bytes",
        "ETag": etag,
        "Cache-Control": "private, max-age=300",
        "X-Content-Type-Options": "nosniff",
    }

    # Handle Range header
    if range is not None:
        try:
            byte_range = parse_byte_range(range, total_size)
        except ValueError as err:
            return Response(
                status_code=416,
                headers={
                    **base_headers,
                    "Content-Range": f"bytes */{total_size}",
                },
                content=b"",
            )

        if byte_range is None:
            # Unsatisfiable range
            return Response(
                status_code=416,
                headers={
                    **base_headers,
                    "Content-Range": f"bytes */{total_size}",
                },
                content=b"",
            )

        start, end = byte_range
        content_length = (end - start) + 1

        headers = {
            **base_headers,
            "Content-Range": f"bytes {start}-{end}/{total_size}",
            "Content-Length": str(content_length),
        }

        if request.method == "HEAD":
            return Response(
                status_code=206,
                media_type=asset.mime_type,
                headers=headers,
            )

        return StreamingResponse(
            stream_file_chunk(str(file_path), start, content_length),
            status_code=206,
            media_type=asset.mime_type,
            headers=headers,
        )

    # Full file response
    headers = {
        **base_headers,
        "Content-Length": str(total_size),
    }

    if request.method == "HEAD":
        return Response(
            status_code=200,
            media_type=asset.mime_type,
            headers=headers,
        )

    return StreamingResponse(
        stream_file_chunk(str(file_path), 0, total_size),
        status_code=200,
        media_type=asset.mime_type,
        headers=headers,
    )
