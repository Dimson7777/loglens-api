from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.enums import BackgroundJobType
from app.models.user import User
from app.repositories.error_analysis import ErrorAnalysisRepository
from app.repositories.error_group import ErrorGroupRepository
from app.schemas.analysis import ErrorAnalysisResponse
from app.services.jobs import JobService


class AnalysisService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._group_repo = ErrorGroupRepository(session)
        self._analysis_repo = ErrorAnalysisRepository(session)
        self._job_service = JobService(session)

    async def create_analysis_job(self, *, group_id: int, current_user: User) -> str:
        group = await self._group_repo.get_by_id(group_id)
        if group is None:
            raise NotFoundError(resource_name="ErrorGroup")

        job = await self._job_service.create_job(
            job_type=BackgroundJobType.ERROR_GROUP_ANALYSIS,
            payload={"group_id": group_id, "requested_by": current_user.id},
            total_items=1,
            created_by=current_user.id,
            idempotency_key=None,
            scope_key=f"error-group:{group_id}:analysis",
        )
        return job.id

    async def get_latest_analysis(self, *, group_id: int) -> ErrorAnalysisResponse:
        analysis = await self._analysis_repo.get_latest_for_group(error_group_id=group_id)
        if analysis is None:
            raise NotFoundError(resource_name="ErrorAnalysis")
        return ErrorAnalysisResponse.model_validate(analysis)

    async def list_analyses(self, *, group_id: int) -> list[ErrorAnalysisResponse]:
        analyses = await self._analysis_repo.list_for_group(error_group_id=group_id)
        return [ErrorAnalysisResponse.model_validate(item) for item in analyses]
