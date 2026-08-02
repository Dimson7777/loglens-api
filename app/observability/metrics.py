from __future__ import annotations

import time
from collections.abc import Callable
from contextlib import suppress
from typing import Any

import redis.asyncio as redis
from prometheus_client import Counter, Gauge, Histogram
from sqlalchemy import event
from sqlalchemy.engine import Engine

HTTP_REQUESTS_TOTAL = Counter(
    "loglens_http_requests_total",
    "Total HTTP requests handled by the API.",
    ["method", "path", "status_code"],
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "loglens_http_request_duration_seconds",
    "HTTP request latency in seconds.",
    ["method", "path", "status_code"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
APPLICATION_ERRORS_TOTAL = Counter(
    "loglens_application_errors_total",
    "Application error count grouped by type.",
    ["error_type", "path"],
)
DATABASE_QUERY_DURATION_SECONDS = Histogram(
    "loglens_database_query_duration_seconds",
    "Database query latency in seconds.",
    ["operation"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)
DATABASE_AVAILABILITY = Gauge(
    "loglens_database_up",
    "Database dependency availability.",
)
REDIS_COMMAND_DURATION_SECONDS = Histogram(
    "loglens_redis_command_duration_seconds",
    "Redis command latency in seconds.",
    ["command"],
    buckets=(0.0005, 0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1),
)
REDIS_AVAILABILITY = Gauge(
    "loglens_redis_up",
    "Redis dependency availability.",
)
CELERY_TASKS_TOTAL = Counter(
    "loglens_celery_tasks_total",
    "Total Celery task executions grouped by status.",
    ["task_name", "status"],
)
CELERY_TASK_DURATION_SECONDS = Histogram(
    "loglens_celery_task_duration_seconds",
    "Celery task execution time in seconds.",
    ["task_name", "status"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 180),
)
ACTIVE_BACKGROUND_JOBS = Gauge(
    "loglens_active_background_jobs",
    "Number of active background jobs grouped by type.",
    ["job_type"],
)
BACKGROUND_JOBS_CREATED_TOTAL = Counter(
    "loglens_background_jobs_created_total",
    "Background jobs created grouped by type.",
    ["job_type"],
)
BACKGROUND_JOB_DURATION_SECONDS = Histogram(
    "loglens_background_job_duration_seconds",
    "Background job duration in seconds.",
    ["job_type", "status"],
    buckets=(0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 180, 300),
)
LOG_INGESTION_TOTAL = Counter(
    "loglens_log_ingestion_total",
    "Count of ingested log records.",
    ["mode"],
)
AI_ANALYSIS_DURATION_SECONDS = Histogram(
    "loglens_ai_analysis_duration_seconds",
    "AI analysis provider latency in seconds.",
    ["provider", "status"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60),
)

_SQLALCHEMY_METRICS_INSTRUMENTED = False


def observe_http_request(method: str, path: str, status_code: int, duration_seconds: float) -> None:
    labels = {"method": method, "path": path, "status_code": str(status_code)}
    HTTP_REQUESTS_TOTAL.labels(**labels).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(**labels).observe(duration_seconds)


def increment_application_error(error_type: str, path: str) -> None:
    APPLICATION_ERRORS_TOTAL.labels(error_type=error_type, path=path).inc()


def observe_database_query(operation: str, duration_seconds: float) -> None:
    DATABASE_QUERY_DURATION_SECONDS.labels(operation=operation).observe(duration_seconds)


def set_database_availability(is_up: bool) -> None:
    DATABASE_AVAILABILITY.set(1 if is_up else 0)


def observe_redis_command(command: str, duration_seconds: float) -> None:
    REDIS_COMMAND_DURATION_SECONDS.labels(command=command.lower()).observe(duration_seconds)


def set_redis_availability(is_up: bool) -> None:
    REDIS_AVAILABILITY.set(1 if is_up else 0)


def observe_celery_task(task_name: str, status: str, duration_seconds: float) -> None:
    CELERY_TASKS_TOTAL.labels(task_name=task_name, status=status).inc()
    CELERY_TASK_DURATION_SECONDS.labels(task_name=task_name, status=status).observe(
        duration_seconds
    )


def increment_background_jobs_created(job_type: str) -> None:
    BACKGROUND_JOBS_CREATED_TOTAL.labels(job_type=job_type).inc()
    ACTIVE_BACKGROUND_JOBS.labels(job_type=job_type).inc()


def decrement_active_background_jobs(job_type: str) -> None:
    with suppress(ValueError):
        ACTIVE_BACKGROUND_JOBS.labels(job_type=job_type).dec()


def observe_background_job_duration(job_type: str, status: str, duration_seconds: float) -> None:
    BACKGROUND_JOB_DURATION_SECONDS.labels(job_type=job_type, status=status).observe(
        duration_seconds
    )


def observe_log_ingestion(mode: str, count: int) -> None:
    LOG_INGESTION_TOTAL.labels(mode=mode).inc(count)


def observe_ai_analysis_duration(provider: str, status: str, duration_seconds: float) -> None:
    AI_ANALYSIS_DURATION_SECONDS.labels(provider=provider, status=status).observe(duration_seconds)


def instrument_sqlalchemy_engine(engine: Engine) -> None:
    global _SQLALCHEMY_METRICS_INSTRUMENTED
    if _SQLALCHEMY_METRICS_INSTRUMENTED:
        return

    @event.listens_for(engine, "before_cursor_execute")
    def before_cursor_execute(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        del conn, cursor, parameters, executemany
        context._loglens_query_started_at = time.perf_counter()
        operation = statement.split(maxsplit=1)[0].lower() if statement else "unknown"
        context._loglens_operation = operation

    @event.listens_for(engine, "after_cursor_execute")
    def after_cursor_execute(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        del conn, cursor, statement, parameters, executemany
        started_at = getattr(context, "_loglens_query_started_at", None)
        operation = getattr(context, "_loglens_operation", "unknown")
        if isinstance(started_at, float):
            observe_database_query(operation, time.perf_counter() - started_at)

    _SQLALCHEMY_METRICS_INSTRUMENTED = True


class MetricsRedis(redis.Redis):  # type: ignore[type-arg]
    async def execute_command(self, *args: Any, **options: Any) -> Any:
        command_name = str(args[0]) if args else "unknown"
        started_at = time.perf_counter()
        try:
            return await super().execute_command(*args, **options)  # type: ignore[no-untyped-call]
        finally:
            observe_redis_command(command_name, time.perf_counter() - started_at)


def timed(operation: Callable[[], Any]) -> tuple[Any, float]:
    started_at = time.perf_counter()
    result = operation()
    return result, time.perf_counter() - started_at
