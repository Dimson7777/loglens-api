from __future__ import annotations

import time
from contextlib import suppress
from typing import Any

import structlog
from celery import Celery, signals

from app.core.config import Settings
from app.observability.metrics import observe_celery_task
from app.observability.tracing import get_current_trace_id, instrument_celery

logger = structlog.get_logger(__name__)

_CELERY_SIGNALS_REGISTERED = False


def setup_celery_observability(celery_app: Celery, settings: Settings) -> None:
    del celery_app
    global _CELERY_SIGNALS_REGISTERED
    if _CELERY_SIGNALS_REGISTERED:
        return

    if settings.otel_enabled:
        instrument_celery()

    @signals.task_prerun.connect  # type: ignore[misc]
    def _task_prerun(
        sender: Any = None,
        task_id: str | None = None,
        task: Any = None,
        args: tuple[object, ...] | None = None,
        kwargs: dict[str, object] | None = None,
        **extra: object,
    ) -> None:
        del sender, args, kwargs, extra
        if task is None:
            return
        task.request._loglens_started_at = time.perf_counter()
        logger.info(
            "celery_task_started",
            task_id=task_id,
            task_name=task.name,
            trace_id=get_current_trace_id(),
        )

    @signals.task_postrun.connect  # type: ignore[misc]
    def _task_postrun(
        sender: Any = None,
        task_id: str | None = None,
        task: Any = None,
        state: str | None = None,
        retval: object = None,
        **extra: object,
    ) -> None:
        del sender, retval, extra
        if task is None:
            return
        started_at = getattr(task.request, "_loglens_started_at", None)
        if not isinstance(started_at, float):
            return
        status = (state or "unknown").lower()
        observe_celery_task(task.name, status, time.perf_counter() - started_at)

    @signals.task_failure.connect  # type: ignore[misc]
    def _task_failure(
        sender: Any = None,
        task_id: str | None = None,
        exception: BaseException | None = None,
        args: tuple[object, ...] | None = None,
        kwargs: dict[str, object] | None = None,
        traceback: object = None,
        einfo: object = None,
        **extra: object,
    ) -> None:
        del sender, args, kwargs, traceback, einfo, extra
        logger.error(
            "celery_task_failed",
            task_id=task_id,
            error=str(exception) if exception else None,
            trace_id=get_current_trace_id(),
        )

    @signals.worker_process_init.connect  # type: ignore[misc]
    def _worker_process_init(**extra: object) -> None:
        del extra
        with suppress(Exception):
            instrument_celery()

    _CELERY_SIGNALS_REGISTERED = True
