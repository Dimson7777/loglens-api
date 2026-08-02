from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db_session
from app.services.analysis import AnalysisService
from app.services.error_groups import ErrorGroupService
from app.services.jobs import JobService
from app.services.logs import LogService


def get_log_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> LogService:
    return LogService(session=session)


def get_error_group_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ErrorGroupService:
    return ErrorGroupService(session=session)


def get_job_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> JobService:
    return JobService(session=session)


def get_analysis_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AnalysisService:
    return AnalysisService(session=session)
