"""FastAPI application factory with security middleware and RFC 7807 error handling."""

from __future__ import annotations

import uuid
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from warehouse_ai.api.errors import (
    ProblemError,
    generic_exception_handler,
    problem_exception_handler,
    validation_exception_handler,
)
from warehouse_ai.api.routes import (
    analytics,
    camera_profiles,
    events,
    health,
    jobs,
    media,
    runs,
    videos,
)
from warehouse_ai.config import Settings, get_settings


class SecurityAndCorrelationMiddleware(BaseHTTPMiddleware):
    """Injects request_id correlation and baseline security headers per Section 20.3."""

    async def dispatch(self, request: Request, call_next: object) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = request_id

        response: Response = await call_next(request)  # type: ignore

        response.headers["x-request-id"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        return response


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure FastAPI application."""
    app_settings = settings or get_settings()

    app = FastAPI(
        title="Warehouse AI Video Intelligence API",
        version="0.1.0",
        description="Warehouse handling video intelligence API prototype",
        docs_url="/docs" if app_settings.APP_ENV.value == "development" else None,
        redoc_url=None,
    )

    # CORS configuration per Section 20.3: exactly WEB_ORIGIN, credentials disabled
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[app_settings.WEB_ORIGIN],
        allow_credentials=False,
        allow_methods=["GET", "POST", "DELETE", "HEAD", "OPTIONS"],
        allow_headers=["*"],
    )

    # Security headers and request ID
    app.add_middleware(SecurityAndCorrelationMiddleware)

    # Exception handlers
    app.add_exception_handler(ProblemError, problem_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    # Mount routers
    app.include_router(health.router)
    app.include_router(videos.router)
    app.include_router(camera_profiles.router)
    app.include_router(runs.router)
    app.include_router(jobs.router)
    app.include_router(events.router)
    app.include_router(media.router)
    app.include_router(analytics.router)

    return app


# Default app instance
app = create_app()
