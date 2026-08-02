from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from typing import Any

import structlog
from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import BackgroundJobStatus
from app.observability.metrics import (
    decrement_active_background_jobs,
    observe_background_job_duration,
    observe_log_ingestion,
)
from app.repositories.background_job import BackgroundJobRepository
from app.schemas.log import BulkLogIngestRequest, BulkLogItemFailure
from app.services.jobs import JobService
from app.services.logs import LogService
from app.workers.tasks._common import LoggedTask, ensure_worker_logging, session_scope

logger = structlog.get_logger(__name__)


@shared_task(bind=True, base=LoggedTask)  # type: ignore[untyped-decorator]
def process_bulk_ingestion_job_task(self: LoggedTask, job_id: str) -> dict[str, Any]:
    ensure_worker_logging()
    return asyncio.run(_process_bulk_ingestion_job(job_id, celery_task_id=self.request.id))


async def _process_bulk_ingestion_job(
    job_id: str,
    *,
    celery_task_id: str | None,
    session: AsyncSession | None = None,
) -> dict[str, Any]:
    if session is not None:
        return await _process_bulk_ingestion_job_with_session(
            session,
            job_id,
            celery_task_id=celery_task_id,
        )

    async with session_scope() as session:
        return await _process_bulk_ingestion_job_with_session(
            session,
            job_id,
            celery_task_id=celery_task_id,
        )


async def _process_bulk_ingestion_job_with_session(
    session: AsyncSession,
    job_id: str,
    *,
    celery_task_id: str | None,
) -> dict[str, Any]:
    started_at = time.perf_counter()
    job_repo = BackgroundJobRepository(session)
    job = await job_repo.get_by_id(job_id)
    if job is None:
        logger.warning("Bulk ingestion job not found", job_id=job_id)
        return {"status": "missing"}

    if job.status in {BackgroundJobStatus.COMPLETED, BackgroundJobStatus.PARTIALLY_COMPLETED}:
        logger.info("Bulk ingestion job already completed", job_id=job_id)
        return {"status": job.status.value}

    await job_repo.mark_running(job, celery_task_id=celery_task_id)
    await session.commit()

    failures: list[BulkLogItemFailure] = []
    success_count = 0
    payload = BulkLogIngestRequest.model_validate(job.payload)
    service = LogService(session)

    for index, item in enumerate(payload.logs):
        try:
            async with session.begin_nested():
                await service._persist_log(item)
            success_count += 1
        except Exception as exc:
            failures.append(BulkLogItemFailure(index=index, error=str(exc)[:200]))

        await job_repo.update_progress(
            job,
            processed_items=index + 1,
            success_count=success_count,
            failure_count=len(failures),
            payload={
                **job.payload,
                "failures": [failure.model_dump(mode="json") for failure in failures],
            },
        )
        await session.commit()

    final_status = JobService.final_status(
        success_count=success_count,
        failure_count=len(failures),
    )
    if final_status == BackgroundJobStatus.FAILED:
        final_status = (
            BackgroundJobStatus.PARTIALLY_COMPLETED if payload.logs else BackgroundJobStatus.FAILED
        )

    await job_repo.mark_completed(
        job,
        status=final_status,
        error_summary=None if not failures else f"{len(failures)} items failed",
    )
    await session.commit()

    logger.info(
        "Bulk ingestion job completed",
        job_id=job_id,
        success_count=success_count,
        failure_count=len(failures),
    )
    observe_log_ingestion("bulk", success_count)
    observe_background_job_duration(
        job.job_type.value,
        final_status.value,
        time.perf_counter() - started_at,
    )
    decrement_active_background_jobs(job.job_type.value)
    return {
        "job_id": job_id,
        "success_count": success_count,
        "failure_count": len(failures),
        "status": final_status.value,
        "completed_at": datetime.now(UTC).isoformat(),
    }
