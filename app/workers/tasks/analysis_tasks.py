from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from typing import Any

import structlog
from celery import shared_task
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.integrations.ai.mock_provider import MockAIProvider
from app.integrations.ai.openai_compatible_provider import OpenAICompatibleProvider
from app.models.enums import BackgroundJobStatus, ErrorAnalysisStatus
from app.models.log import Log
from app.observability.metrics import (
    decrement_active_background_jobs,
    observe_ai_analysis_duration,
    observe_background_job_duration,
)
from app.repositories.background_job import BackgroundJobRepository
from app.repositories.error_analysis import ErrorAnalysisRepository
from app.repositories.error_group import ErrorGroupRepository
from app.services.ai_prompt import build_analysis_prompts
from app.workers.tasks._common import LoggedTask, ensure_worker_logging, session_scope

logger = structlog.get_logger(__name__)


def _build_provider() -> MockAIProvider | OpenAICompatibleProvider:
    settings = get_settings()
    if settings.ai_provider == "openai_compatible":
        return OpenAICompatibleProvider(settings)
    return MockAIProvider()


@shared_task(bind=True, base=LoggedTask)  # type: ignore[untyped-decorator]
def run_error_group_analysis_task(self: LoggedTask, job_id: str) -> dict[str, Any]:
    ensure_worker_logging()
    return asyncio.run(_run_error_group_analysis(job_id, celery_task_id=self.request.id))


async def _run_error_group_analysis(
    job_id: str,
    *,
    celery_task_id: str | None,
    session: AsyncSession | None = None,
) -> dict[str, Any]:
    if session is not None:
        return await _run_error_group_analysis_with_session(
            session,
            job_id,
            celery_task_id=celery_task_id,
        )

    async with session_scope() as session:
        return await _run_error_group_analysis_with_session(
            session,
            job_id,
            celery_task_id=celery_task_id,
        )


async def _run_error_group_analysis_with_session(
    session: AsyncSession,
    job_id: str,
    *,
    celery_task_id: str | None,
) -> dict[str, Any]:
    settings = get_settings()
    started_at = time.perf_counter()

    job_repo = BackgroundJobRepository(session)
    analysis_repo = ErrorAnalysisRepository(session)
    group_repo = ErrorGroupRepository(session)

    job = await job_repo.get_by_id(job_id)
    if job is None:
        logger.warning("Analysis job missing", job_id=job_id)
        return {"status": "missing"}

    if job.status in {BackgroundJobStatus.COMPLETED, BackgroundJobStatus.PARTIALLY_COMPLETED}:
        return {"status": job.status.value}

    await job_repo.mark_running(job, celery_task_id=celery_task_id)

    group_id = int(job.payload["group_id"])
    created_by = int(job.payload["requested_by"])
    group = await group_repo.get_by_id(group_id)
    if group is None:
        await job_repo.mark_failed(job, error_summary="Error group not found")
        await session.commit()
        return {"status": "failed"}

    await analysis_repo.create_pending_analysis(
        error_group_id=group_id,
        created_by=created_by,
    )
    await session.commit()

    provider = _build_provider()

    job = await job_repo.get_by_id(job_id)
    assert job is not None

    stmt = (
        select(Log)
        .where(Log.error_group_id == int(job.payload["group_id"]))
        .order_by(desc(Log.timestamp), desc(Log.id))
        .limit(10)
    )
    logs = list(await session.scalars(stmt))

    group = await group_repo.get_by_id(int(job.payload["group_id"]))
    assert group is not None

    system_prompt, user_prompt = build_analysis_prompts(settings=settings, group=group, logs=logs)

    latest = await analysis_repo.get_latest_for_group(error_group_id=group.id)
    assert latest is not None

    try:
        provider_started_at = time.perf_counter()
        result = await provider.analyze_error_group(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        observe_ai_analysis_duration(
            result.provider,
            "success",
            time.perf_counter() - provider_started_at,
        )
        latest.status = ErrorAnalysisStatus.COMPLETED
        latest.summary = result.summary
        latest.likely_root_cause = result.likely_root_cause
        latest.suggested_fix = result.suggested_fix
        latest.confidence = result.confidence
        latest.affected_component = result.affected_component
        latest.recommended_priority = result.recommended_priority
        latest.reasoning_summary = result.reasoning_summary
        latest.provider = result.provider
        latest.model = result.model
        latest.latency_ms = result.latency_ms
        latest.raw_response_metadata = {
            "generated_at": result.generated_at.isoformat(),
            "log_count": len(logs),
        }
        latest.completed_at = datetime.now(UTC)
        await job_repo.update_progress(
            job,
            processed_items=1,
            success_count=1,
            failure_count=0,
        )
        await job_repo.mark_completed(job, status=BackgroundJobStatus.COMPLETED)
    except Exception:
        observe_ai_analysis_duration(settings.ai_provider, "failure", 0.0)
        latest.status = ErrorAnalysisStatus.FAILED
        await job_repo.update_progress(
            job,
            processed_items=1,
            success_count=0,
            failure_count=1,
        )
        await job_repo.mark_completed(
            job,
            status=BackgroundJobStatus.FAILED,
            error_summary="Analysis failed",
        )
    observe_background_job_duration(
        job.job_type.value,
        job.status.value,
        time.perf_counter() - started_at,
    )
    decrement_active_background_jobs(job.job_type.value)
    await session.commit()

    return {"job_id": job_id}
