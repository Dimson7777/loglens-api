import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from structlog.contextvars import bind_contextvars, clear_contextvars, unbind_contextvars

from app.observability.metrics import increment_application_error, observe_http_request
from app.observability.tracing import get_current_trace_id

logger = structlog.get_logger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        clear_contextvars()
        bind_contextvars(request_id=request_id)

        start_time = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            duration_seconds = time.perf_counter() - start_time
            duration_ms = round(duration_seconds * 1000, 2)
            trace_id = get_current_trace_id()
            if trace_id is not None:
                bind_contextvars(trace_id=trace_id)
            increment_application_error(type(exc).__name__, request.url.path)
            observe_http_request(request.method, request.url.path, 500, duration_seconds)
            logger.exception(
                "request_failed",
                request_id=request_id,
                trace_id=trace_id,
                method=request.method,
                path=request.url.path,
                duration_ms=duration_ms,
            )
            unbind_contextvars("request_id", "trace_id")
            raise

        duration_seconds = time.perf_counter() - start_time
        duration_ms = round(duration_seconds * 1000, 2)
        trace_id = get_current_trace_id()
        if trace_id is not None:
            bind_contextvars(trace_id=trace_id)
        observe_http_request(
            request.method, request.url.path, response.status_code, duration_seconds
        )

        logger.info(
            "request_completed",
            request_id=request_id,
            trace_id=trace_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )

        response.headers["X-Request-ID"] = request_id
        if trace_id is not None:
            response.headers["X-Trace-ID"] = trace_id
        unbind_contextvars("request_id", "trace_id")
        return response
