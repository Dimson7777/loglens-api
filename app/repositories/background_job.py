from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.background_job import BackgroundJob
from app.models.enums import BackgroundJobStatus, BackgroundJobType


class BackgroundJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, job_id: str) -> BackgroundJob | None:
        return await self._session.get(BackgroundJob, job_id)

    async def create_job(
        self,
        *,
        job_id: str,
        job_type: BackgroundJobType,
        payload: dict[str, object],
        total_items: int,
        created_by: int | None,
        idempotency_key: str | None,
        scope_key: str | None,
    ) -> BackgroundJob:
        job = BackgroundJob(
            id=job_id,
            job_type=job_type,
            status=BackgroundJobStatus.PENDING,
            payload=payload,
            total_items=total_items,
            created_by=created_by,
            idempotency_key=idempotency_key,
            scope_key=scope_key,
        )
        self._session.add(job)
        await self._session.flush()
        await self._session.refresh(job)
        return job

    async def get_by_job_type_and_idempotency_key(
        self,
        *,
        job_type: BackgroundJobType,
        idempotency_key: str,
    ) -> BackgroundJob | None:
        stmt: Select[tuple[BackgroundJob]] = select(BackgroundJob).where(
            BackgroundJob.job_type == job_type,
            BackgroundJob.idempotency_key == idempotency_key,
        )
        result = await self._session.scalars(stmt.limit(1))
        return result.first()

    async def get_active_by_scope(
        self,
        *,
        job_type: BackgroundJobType,
        scope_key: str,
    ) -> BackgroundJob | None:
        stmt: Select[tuple[BackgroundJob]] = select(BackgroundJob).where(
            BackgroundJob.job_type == job_type,
            BackgroundJob.scope_key == scope_key,
            BackgroundJob.status.in_([BackgroundJobStatus.PENDING, BackgroundJobStatus.RUNNING]),
        )
        result = await self._session.scalars(stmt.limit(1))
        return result.first()

    async def mark_running(
        self, job: BackgroundJob, *, celery_task_id: str | None
    ) -> BackgroundJob:
        if job.started_at is None:
            job.started_at = datetime.now(UTC)
        job.status = BackgroundJobStatus.RUNNING
        job.celery_task_id = celery_task_id
        await self._session.flush()
        await self._session.refresh(job)
        return job

    async def update_progress(
        self,
        job: BackgroundJob,
        *,
        processed_items: int,
        success_count: int,
        failure_count: int,
        payload: dict[str, object] | None = None,
        error_summary: str | None = None,
    ) -> BackgroundJob:
        job.processed_items = processed_items
        job.success_count = success_count
        job.failure_count = failure_count
        if payload is not None:
            job.payload = payload
        if error_summary is not None:
            job.error_summary = error_summary
        await self._session.flush()
        await self._session.refresh(job)
        return job

    async def mark_completed(
        self,
        job: BackgroundJob,
        *,
        status: BackgroundJobStatus,
        error_summary: str | None = None,
    ) -> BackgroundJob:
        job.status = status
        job.completed_at = datetime.now(UTC)
        job.error_summary = error_summary
        await self._session.flush()
        await self._session.refresh(job)
        return job

    async def mark_failed(self, job: BackgroundJob, *, error_summary: str) -> BackgroundJob:
        job.status = BackgroundJobStatus.FAILED
        job.error_summary = error_summary
        job.completed_at = datetime.now(UTC)
        await self._session.flush()
        await self._session.refresh(job)
        return job
