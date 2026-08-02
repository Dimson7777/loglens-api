from __future__ import annotations

from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.background_job import BackgroundJob
from app.models.enums import BackgroundJobStatus, BackgroundJobType
from app.observability.metrics import increment_background_jobs_created
from app.repositories.background_job import BackgroundJobRepository
from app.schemas.job import JobAcceptedResponse, JobStatusResponse


class JobService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._job_repo = BackgroundJobRepository(session)

    async def create_job(
        self,
        *,
        job_type: BackgroundJobType,
        payload: dict[str, object],
        total_items: int,
        created_by: int | None,
        idempotency_key: str | None = None,
        scope_key: str | None = None,
    ) -> BackgroundJob:
        if idempotency_key is not None:
            existing = await self._job_repo.get_by_job_type_and_idempotency_key(
                job_type=job_type,
                idempotency_key=idempotency_key,
            )
            if existing is not None:
                existing_hash = existing.payload.get("request_hash")
                incoming_hash = payload.get("request_hash")
                if (
                    existing_hash is not None
                    and incoming_hash is not None
                    and existing_hash != incoming_hash
                ):
                    raise ConflictError("Idempotency key was already used for a different request.")
                return existing

        if scope_key is not None:
            active = await self._job_repo.get_active_by_scope(
                job_type=job_type, scope_key=scope_key
            )
            if active is not None:
                raise ConflictError("A job is already running for this resource.")

        job = await self._job_repo.create_job(
            job_id=str(uuid4()),
            job_type=job_type,
            payload=payload,
            total_items=total_items,
            created_by=created_by,
            idempotency_key=idempotency_key,
            scope_key=scope_key,
        )
        increment_background_jobs_created(job_type.value)
        await self._session.commit()
        return job

    async def get_job(self, job_id: str) -> BackgroundJob:
        job = await self._job_repo.get_by_id(job_id)
        if job is None:
            raise NotFoundError(resource_name="BackgroundJob")
        return job

    async def get_job_status(self, job_id: str) -> JobStatusResponse:
        job = await self.get_job(job_id)
        return JobStatusResponse(
            job_id=job.id,
            status=job.status,
            total_items=job.total_items,
            processed_items=job.processed_items,
            success_count=job.success_count,
            failure_count=job.failure_count,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            error_summary=job.error_summary,
        )

    @staticmethod
    def to_accepted_response(job: BackgroundJob) -> JobAcceptedResponse:
        return JobAcceptedResponse(job_id=job.id, status=job.status)

    @staticmethod
    def final_status(*, success_count: int, failure_count: int) -> BackgroundJobStatus:
        if failure_count == 0:
            return BackgroundJobStatus.COMPLETED
        if success_count == 0:
            return BackgroundJobStatus.FAILED
        return BackgroundJobStatus.PARTIALLY_COMPLETED
