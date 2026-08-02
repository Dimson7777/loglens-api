from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import uuid4

import httpx
import pytest
from _pytest.monkeypatch import MonkeyPatch
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.exceptions import ConflictError, ServiceUnavailableError
from app.core.redis import get_redis_client
from app.integrations.ai.mock_provider import MockAIProvider
from app.integrations.ai.openai_compatible_provider import OpenAICompatibleProvider
from app.models.background_job import BackgroundJob
from app.models.enums import BackgroundJobStatus, BackgroundJobType, LogEnvironment, LogLevel
from app.models.log import Log
from app.services.jobs import JobService
from app.workers.celery_app import celery_app
from app.workers.tasks.analytics_tasks import _ANALYTICS_CACHE_KEY, _recalculate_summary_analytics
from app.workers.tasks.cleanup_tasks import _cleanup_old_logs
from app.workers.tasks.log_tasks import _process_bulk_ingestion_job


@pytest.mark.asyncio
async def test_celery_uses_eager_mode() -> None:
    assert bool(celery_app.conf.task_always_eager) is True


@pytest.mark.asyncio
async def test_mock_provider_returns_valid_shape() -> None:
    provider = MockAIProvider()
    result = await provider.analyze_error_group(system_prompt="safe", user_prompt="database error")
    assert 0.0 <= result.confidence <= 1.0
    assert result.provider == "mock"


@pytest.mark.asyncio
async def test_openai_provider_malformed_json_raises() -> None:
    settings = get_settings()
    settings.ai_openai_api_key = "test-key"
    settings.ai_openai_base_url = "https://example.test/v1"
    provider = OpenAICompatibleProvider(settings)

    class _BadResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"choices": [{"message": {"content": "not-json"}}]}

    class _Client:
        def __init__(self, *args: object, **kwargs: object) -> None:
            del args, kwargs

        async def __aenter__(self) -> _Client:
            return self

        async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
            del exc_type, exc, tb

        async def post(self, *args: object, **kwargs: object) -> _BadResponse:
            del args, kwargs
            return _BadResponse()

    patch = MonkeyPatch()
    patch.setattr(httpx, "AsyncClient", cast(type[httpx.AsyncClient], _Client))
    try:
        with pytest.raises(ServiceUnavailableError):
            await provider.analyze_error_group(system_prompt="safe", user_prompt="untrusted")
    finally:
        patch.undo()


@pytest.mark.asyncio
async def test_duplicate_scope_job_prevention(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        service = JobService(session)
        await service.create_job(
            job_type=BackgroundJobType.ERROR_GROUP_ANALYSIS,
            payload={"group_id": 1, "requested_by": 1},
            total_items=1,
            created_by=None,
            scope_key="error-group:1:analysis",
        )

    async with session_factory() as session:
        service = JobService(session)
        with pytest.raises(ConflictError):
            await service.create_job(
                job_type=BackgroundJobType.ERROR_GROUP_ANALYSIS,
                payload={"group_id": 1, "requested_by": 1},
                total_items=1,
                created_by=None,
                scope_key="error-group:1:analysis",
            )


@pytest.mark.asyncio
async def test_bulk_task_partial_failures(
    session_factory: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import logs as logs_module

    original = logs_module.LogService._persist_log

    async def _patched(self: logs_module.LogService, payload: Any) -> Log:
        message = cast(str, payload.message)
        if "fail-me" in message:
            raise RuntimeError("simulated failure")
        return await original(self, payload)

    monkeypatch.setattr(logs_module.LogService, "_persist_log", _patched)

    job_id = ""
    async with session_factory() as session:
        job_service = JobService(session)
        created_job = await job_service.create_job(
            job_type=BackgroundJobType.BULK_LOG_INGEST,
            payload={
                "request_hash": "hash-1",
                "logs": [
                    {
                        "service_name": "svc",
                        "environment": LogEnvironment.PRODUCTION.value,
                        "log_level": LogLevel.ERROR.value,
                        "message": "ok-item",
                        "exception_type": None,
                        "stack_trace": None,
                        "metadata": {},
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                    {
                        "service_name": "svc",
                        "environment": LogEnvironment.PRODUCTION.value,
                        "log_level": LogLevel.ERROR.value,
                        "message": "fail-me",
                        "exception_type": None,
                        "stack_trace": None,
                        "metadata": {},
                        "timestamp": datetime.now(UTC).isoformat(),
                    },
                ],
            },
            total_items=2,
            created_by=None,
            idempotency_key=str(uuid4()),
        )
        job_id = created_job.id

    async with session_factory() as session:
        await _process_bulk_ingestion_job(
            job_id,
            celery_task_id="test-task-id",
            session=session,
        )

    async with session_factory() as session:
        row = await session.get(BackgroundJob, job_id)
        assert row is not None
        assert row.status == BackgroundJobStatus.PARTIALLY_COMPLETED
        assert row.success_count == 1
        assert row.failure_count == 1


@pytest.mark.asyncio
async def test_cleanup_dry_run_preserves_rows(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    old_timestamp = datetime.now(UTC) - timedelta(days=120)
    async with session_factory() as session:
        session.add(
            Log(
                service_name="cleanup-svc",
                environment=LogEnvironment.PRODUCTION,
                log_level=LogLevel.ERROR,
                message="old",
                normalized_message="old",
                exception_type=None,
                stack_trace=None,
                metadata_={},
                fingerprint=None,
                error_group_id=None,
                timestamp=old_timestamp,
            )
        )
        await session.commit()

    result = await _cleanup_old_logs(dry_run=True, session_factory=session_factory)
    assert bool(result["dry_run"]) is True
    assert int(result["deleted_count"]) >= 1

    async with session_factory() as session:
        remaining = list(
            await session.scalars(select(Log).where(Log.service_name == "cleanup-svc"))
        )
        assert len(remaining) == 1


@pytest.mark.asyncio
async def test_analytics_cache_refresh(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        session.add(
            Log(
                service_name="analytics-svc",
                environment=LogEnvironment.PRODUCTION,
                log_level=LogLevel.INFO,
                message="recent",
                normalized_message="recent",
                exception_type=None,
                stack_trace=None,
                metadata_={},
                fingerprint=None,
                error_group_id=None,
                timestamp=datetime.now(UTC),
            )
        )
        await session.commit()

    payload = await _recalculate_summary_analytics(session_factory=session_factory)
    redis = get_redis_client()
    cached = await redis.get(_ANALYTICS_CACHE_KEY)
    assert cached is not None
    assert payload["logs_last_24h"] >= 1
