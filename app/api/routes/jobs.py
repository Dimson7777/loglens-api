from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies.auth import require_developer_or_admin
from app.api.dependencies.logs import get_job_service
from app.models.user import User
from app.schemas.job import JobStatusResponse
from app.services.jobs import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    _: Annotated[User, Depends(require_developer_or_admin)],
    job_service: Annotated[JobService, Depends(get_job_service)],
) -> JobStatusResponse:
    return await job_service.get_job_status(job_id)
