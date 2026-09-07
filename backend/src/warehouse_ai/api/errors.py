"""RFC 7807 application/problem+json error formatting and exception handlers matching Blueprint Section 15.3."""

from __future__ import annotations

import uuid
from typing import Any
from fastapi import HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ProblemError(HTTPException):
    """Base HTTP exception conforming to RFC 7807 problem+json."""

    def __init__(
        self,
        status_code: int,
        code: str,
        title: str,
        detail: str,
        errors: list[dict[str, Any]] | None = None,
        problem_type: str | None = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail)
        self.code = code
        self.title = title
        self.detail_msg = detail
        self.errors = errors or []
        self.problem_type = problem_type or f"https://warehouse-ai.local/problems/{code.lower().replace('_', '-')}"


def create_problem_response(
    status_code: int,
    code: str,
    title: str,
    detail: str,
    request_id: str | None = None,
    errors: list[dict[str, Any]] | None = None,
    problem_type: str | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Build a JSONResponse with application/problem+json content type."""
    req_id = request_id or str(uuid.uuid4())
    p_type = problem_type or f"https://warehouse-ai.local/problems/{code.lower().replace('_', '-')}"
    payload: dict[str, Any] = {
        "type": p_type,
        "title": title,
        "status": status_code,
        "detail": detail,
        "code": code,
        "request_id": req_id,
        "errors": errors or [],
    }

    resp_headers = headers or {}
    return JSONResponse(
        status_code=status_code,
        content=payload,
        media_type="application/problem+json",
        headers=resp_headers,
    )


async def problem_exception_handler(request: Request, exc: ProblemError) -> JSONResponse:
    req_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())
    return create_problem_response(
        status_code=exc.status_code,
        code=exc.code,
        title=exc.title,
        detail=exc.detail_msg,
        request_id=req_id,
        errors=exc.errors,
        problem_type=exc.problem_type,
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    req_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())
    error_list = []
    for err in exc.errors():
        loc = ".".join(str(x) for x in err.get("loc", []))
        msg = err.get("msg", "Invalid value")
        error_list.append({"field": loc, "reason": msg})

    return create_problem_response(
        status_code=422,
        code="VALIDATION_ERROR",
        title="Request validation failed",
        detail="The request payload did not satisfy validation rules.",
        request_id=req_id,
        errors=error_list,
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    req_id = getattr(request.state, "request_id", None) or str(uuid.uuid4())
    return create_problem_response(
        status_code=500,
        code="INTERNAL_ERROR",
        title="Internal server error",
        detail="An unhandled internal server error occurred.",
        request_id=req_id,
        errors=[],
    )
