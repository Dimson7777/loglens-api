from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from celery import Task
from celery.exceptions import Ignore
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.repositories.background_job import BackgroundJobRepository

_logger = structlog.get_logger(__name__)


def ensure_worker_logging() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, settings.json_logs)


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    from app.database.session import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
        finally:
            await session.close()


class LoggedTask(Task):  # type: ignore[misc]
    autoretry_for = (Exception,)
    retry_backoff = True
    retry_backoff_max = 60
    retry_jitter = True
    max_retries = 5

    def on_retry(
        self,
        exc: BaseException,
        task_id: str,
        args: tuple[object, ...],
        kwargs: dict[str, object],
        einfo: object,
    ) -> None:
        _logger.warning(
            "Task retry scheduled",
            task_name=self.name,
            task_id=task_id,
            error=str(exc),
            retry_count=self.request.retries,
        )
        super().on_retry(exc, task_id, args, kwargs, einfo)

    def on_failure(
        self,
        exc: BaseException,
        task_id: str,
        args: tuple[object, ...],
        kwargs: dict[str, object],
        einfo: object,
    ) -> None:
        _logger.error(
            "Task failed",
            task_name=self.name,
            task_id=task_id,
            error=str(exc),
        )
        super().on_failure(exc, task_id, args, kwargs, einfo)


async def set_job_failed(job_id: str, error_summary: str) -> None:
    async with session_scope() as session:
        repo = BackgroundJobRepository(session)
        job = await repo.get_by_id(job_id)
        if job is None:
            return
        await repo.mark_failed(job, error_summary=error_summary)
        await session.commit()


def fail_and_ignore(job_id: str, error_summary: str) -> None:
    asyncio.run(set_job_failed(job_id, error_summary))
    raise Ignore()
