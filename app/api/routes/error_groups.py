from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import require_admin_user, require_developer_or_admin
from app.api.dependencies.logs import get_analysis_service, get_error_group_service
from app.database.session import get_db_session
from app.models.enums import BackgroundJobStatus
from app.models.user import User
from app.schemas.analysis import ErrorAnalysisResponse
from app.schemas.common import ErrorEnvelope
from app.schemas.error_group import (
    ErrorGroupAssignmentUpdateRequest,
    ErrorGroupListQuery,
    ErrorGroupListResponse,
    ErrorGroupResponse,
    ErrorGroupStatusUpdateRequest,
)
from app.schemas.job import JobAcceptedResponse
from app.services.analysis import AnalysisService
from app.services.error_groups import ErrorGroupService
from app.workers.celery_app import celery_app
from app.workers.tasks.analysis_tasks import (
    _run_error_group_analysis,
    run_error_group_analysis_task,
)

router = APIRouter(prefix="/error-groups", tags=["error-groups"])


@router.get("", response_model=ErrorGroupListResponse)
async def list_error_groups(
    query: Annotated[ErrorGroupListQuery, Depends(ErrorGroupListQuery)],
    _: Annotated[User, Depends(require_developer_or_admin)],
    error_group_service: Annotated[ErrorGroupService, Depends(get_error_group_service)],
) -> ErrorGroupListResponse:
    return await error_group_service.list_error_groups(query)


@router.get("/{group_id}", response_model=ErrorGroupResponse)
async def get_error_group(
    group_id: int,
    _: Annotated[User, Depends(require_developer_or_admin)],
    error_group_service: Annotated[ErrorGroupService, Depends(get_error_group_service)],
) -> ErrorGroupResponse:
    group = await error_group_service.get_error_group(group_id)
    return ErrorGroupResponse.model_validate(group)


@router.patch(
    "/{group_id}/status",
    response_model=ErrorGroupResponse,
    responses={403: {"model": ErrorEnvelope}, 404: {"model": ErrorEnvelope}},
)
async def update_error_group_status(
    group_id: int,
    payload: ErrorGroupStatusUpdateRequest,
    _: Annotated[User, Depends(require_admin_user)],
    error_group_service: Annotated[ErrorGroupService, Depends(get_error_group_service)],
) -> ErrorGroupResponse:
    group = await error_group_service.update_status(group_id=group_id, payload=payload)
    return ErrorGroupResponse.model_validate(group)


@router.patch(
    "/{group_id}/assignment",
    response_model=ErrorGroupResponse,
    responses={403: {"model": ErrorEnvelope}, 404: {"model": ErrorEnvelope}},
)
async def update_error_group_assignment(
    group_id: int,
    payload: ErrorGroupAssignmentUpdateRequest,
    current_user: Annotated[User, Depends(require_developer_or_admin)],
    error_group_service: Annotated[ErrorGroupService, Depends(get_error_group_service)],
) -> ErrorGroupResponse:
    group = await error_group_service.update_assignment(
        group_id=group_id,
        payload=payload,
        current_user=current_user,
    )
    return ErrorGroupResponse.model_validate(group)


@router.post(
    "/{group_id}/analyze",
    status_code=202,
    response_model=JobAcceptedResponse,
    responses={403: {"model": ErrorEnvelope}, 404: {"model": ErrorEnvelope}},
)
async def analyze_error_group(
    group_id: int,
    current_user: Annotated[User, Depends(require_developer_or_admin)],
    analysis_service: Annotated[AnalysisService, Depends(get_analysis_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> JobAcceptedResponse:
    job_id = await analysis_service.create_analysis_job(
        group_id=group_id, current_user=current_user
    )
    if celery_app.conf.task_always_eager:
        await _run_error_group_analysis(job_id, celery_task_id="eager", session=session)
    else:
        run_error_group_analysis_task.delay(job_id)
    return JobAcceptedResponse(job_id=job_id, status=BackgroundJobStatus.PENDING)


@router.get(
    "/{group_id}/analysis",
    response_model=ErrorAnalysisResponse,
    responses={403: {"model": ErrorEnvelope}, 404: {"model": ErrorEnvelope}},
)
async def get_latest_error_group_analysis(
    group_id: int,
    _: Annotated[User, Depends(require_developer_or_admin)],
    analysis_service: Annotated[AnalysisService, Depends(get_analysis_service)],
) -> ErrorAnalysisResponse:
    return await analysis_service.get_latest_analysis(group_id=group_id)


@router.get(
    "/{group_id}/analyses",
    response_model=list[ErrorAnalysisResponse],
    responses={403: {"model": ErrorEnvelope}},
)
async def list_error_group_analyses(
    group_id: int,
    _: Annotated[User, Depends(require_developer_or_admin)],
    analysis_service: Annotated[AnalysisService, Depends(get_analysis_service)],
) -> list[ErrorAnalysisResponse]:
    return await analysis_service.list_analyses(group_id=group_id)
