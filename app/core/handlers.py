from typing import Any, cast

import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.types import ExceptionHandler

from app.core.exceptions import AppError

logger = structlog.get_logger(__name__)


def _trace_id_from_request(request: Request) -> str | None:
    value = getattr(request.state, "request_id", None)
    if isinstance(value, str):
        return value
    return None


def _error_payload(
    *,
    code: str,
    message: str,
    details: dict[str, Any] | list[Any] | None,
    trace_id: str | None,
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details,
        },
        "trace_id": trace_id,
    }


async def app_exception_handler(request: Request, exc: AppError) -> JSONResponse:
    payload = _error_payload(
        code=exc.code,
        message=exc.message,
        details=exc.details,
        trace_id=_trace_id_from_request(request),
    )
    return JSONResponse(status_code=exc.status_code, content=payload)


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    details: dict[str, Any] | list[Any] | None
    if isinstance(exc.detail, (dict, list)):
        details = exc.detail
    elif exc.detail is None:
        details = None
    else:
        details = {"reason": str(exc.detail)}

    payload = _error_payload(
        code="http_error",
        message="Request failed.",
        details=details,
        trace_id=_trace_id_from_request(request),
    )
    return JSONResponse(status_code=exc.status_code, content=payload)


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    payload = _error_payload(
        code="validation_error",
        message="Request validation failed.",
        details=list(exc.errors()),
        trace_id=_trace_id_from_request(request),
    )
    return JSONResponse(status_code=422, content=payload)


async def unexpected_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    trace_id = _trace_id_from_request(request)
    logger.exception("Unhandled exception", trace_id=trace_id)
    payload = _error_payload(
        code="internal_server_error",
        message="An unexpected error occurred.",
        details=None,
        trace_id=trace_id,
    )
    return JSONResponse(status_code=500, content=payload)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, cast(ExceptionHandler, app_exception_handler))
    app.add_exception_handler(HTTPException, cast(ExceptionHandler, http_exception_handler))
    app.add_exception_handler(
        RequestValidationError,
        cast(ExceptionHandler, validation_exception_handler),
    )
    app.add_exception_handler(Exception, unexpected_exception_handler)
