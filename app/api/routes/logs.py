from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth import require_admin_user, require_developer_or_admin
from app.api.dependencies.logs import get_log_service
from app.database.session import get_db_session
from app.models.user import User
from app.schemas.common import ErrorEnvelope
from app.schemas.job import JobAcceptedResponse
from app.schemas.log import (
    BulkLogIngestRequest,
    LogIngestRequest,
    LogListQuery,
    LogListResponse,
    LogResponse,
)
from app.services.logs import LogService
from app.workers.celery_app import celery_app
from app.workers.tasks.log_tasks import _process_bulk_ingestion_job, process_bulk_ingestion_job_task

router = APIRouter(prefix="/logs", tags=["logs"])


@router.post(
    "",
    response_model=LogResponse,
    status_code=status.HTTP_201_CREATED,
    responses={403: {"model": ErrorEnvelope}},
)
async def create_log(
    payload: LogIngestRequest,
    _: Annotated[User, Depends(require_developer_or_admin)],
    log_service: Annotated[LogService, Depends(get_log_service)],
) -> LogResponse:
    log = await log_service.ingest_log(payload)
    return LogResponse.model_validate(log)


@router.post(
    "/bulk",
    response_model=JobAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={403: {"model": ErrorEnvelope}, 409: {"model": ErrorEnvelope}},
)
async def create_bulk_logs(
    payload: BulkLogIngestRequest,
    current_user: Annotated[User, Depends(require_developer_or_admin)],
    log_service: Annotated[LogService, Depends(get_log_service)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> JobAcceptedResponse:
    response = await log_service.enqueue_bulk_ingestion_job(
        payload=payload, current_user=current_user
    )
    if celery_app.conf.task_always_eager:
        await _process_bulk_ingestion_job(
            response.job_id,
            celery_task_id="eager",
            session=session,
        )
    else:
        process_bulk_ingestion_job_task.delay(response.job_id)
    return response


@router.get("", response_model=LogListResponse)
async def list_logs(
    query: Annotated[LogListQuery, Depends(LogListQuery)],
    _: Annotated[User, Depends(require_developer_or_admin)],
    log_service: Annotated[LogService, Depends(get_log_service)],
) -> LogListResponse:
    return await log_service.list_logs(query)


@router.get("/{log_id}", response_model=LogResponse)
async def get_log(
    log_id: int,
    _: Annotated[User, Depends(require_developer_or_admin)],
    log_service: Annotated[LogService, Depends(get_log_service)],
) -> LogResponse:
    log = await log_service.get_log(log_id)
    return LogResponse.model_validate(log)


@router.delete(
    "/{log_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={403: {"model": ErrorEnvelope}, 404: {"model": ErrorEnvelope}},
)
async def delete_log(
    log_id: int,
    _: Annotated[User, Depends(require_admin_user)],
    log_service: Annotated[LogService, Depends(get_log_service)],
) -> None:
    await log_service.delete_log(log_id)
