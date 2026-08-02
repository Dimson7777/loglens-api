from __future__ import annotations

from collections.abc import Mapping
from contextlib import suppress

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.instrumentation.celery import CeleryInstrumentor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
from opentelemetry.trace.span import format_trace_id

from app.core.config import Settings

_TRACING_CONFIGURED = False
_SQLALCHEMY_TRACING_INSTRUMENTED = False
_CELERY_TRACING_INSTRUMENTED = False
_REDIS_TRACING_INSTRUMENTED = False
_HTTPX_TRACING_INSTRUMENTED = False


def _parse_otlp_headers(raw_headers: str) -> Mapping[str, str]:
    pairs = [item.strip() for item in raw_headers.split(",") if item.strip()]
    headers: dict[str, str] = {}
    for pair in pairs:
        key, _, value = pair.partition("=")
        if key and value:
            headers[key.strip()] = value.strip()
    return headers


def setup_tracing(app: FastAPI, settings: Settings) -> None:
    global _TRACING_CONFIGURED
    if not settings.otel_enabled or _TRACING_CONFIGURED:
        return

    resource = Resource.create(
        {
            "service.name": settings.otel_service_name,
            "service.version": settings.release_name,
            "deployment.environment": settings.app_env,
        }
    )
    provider = TracerProvider(
        resource=resource,
        sampler=TraceIdRatioBased(settings.otel_sample_ratio),
    )

    if settings.otel_exporter_otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        exporter = OTLPSpanExporter(
            endpoint=settings.otel_exporter_otlp_endpoint,
            headers=_parse_otlp_headers(settings.otel_exporter_otlp_headers),
            timeout=settings.otel_exporter_timeout_seconds,
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)

    global _REDIS_TRACING_INSTRUMENTED
    global _HTTPX_TRACING_INSTRUMENTED
    if not _REDIS_TRACING_INSTRUMENTED:
        RedisInstrumentor().instrument()
        _REDIS_TRACING_INSTRUMENTED = True
    if not _HTTPX_TRACING_INSTRUMENTED:
        HTTPXClientInstrumentor().instrument()
        _HTTPX_TRACING_INSTRUMENTED = True

    _TRACING_CONFIGURED = True


def instrument_sqlalchemy(sync_engine: object) -> None:
    global _SQLALCHEMY_TRACING_INSTRUMENTED
    if _SQLALCHEMY_TRACING_INSTRUMENTED:
        return
    SQLAlchemyInstrumentor().instrument(engine=sync_engine)
    _SQLALCHEMY_TRACING_INSTRUMENTED = True


def instrument_celery() -> None:
    global _CELERY_TRACING_INSTRUMENTED
    if _CELERY_TRACING_INSTRUMENTED:
        return
    with suppress(Exception):
        CeleryInstrumentor().instrument()
        _CELERY_TRACING_INSTRUMENTED = True


def get_current_trace_id() -> str | None:
    span = trace.get_current_span()
    span_context = span.get_span_context()
    if not span_context.is_valid:
        return None
    return format_trace_id(span_context.trace_id)
