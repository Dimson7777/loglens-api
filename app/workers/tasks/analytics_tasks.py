from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from celery import shared_task
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.redis import get_redis_client
from app.models.enums import ErrorGroupStatus
from app.models.error_group import ErrorGroup
from app.models.log import Log
from app.workers.tasks._common import LoggedTask, ensure_worker_logging

logger = structlog.get_logger(__name__)

_ANALYTICS_CACHE_KEY = "analytics:summary:v1"


@shared_task(bind=True, base=LoggedTask)  # type: ignore[untyped-decorator]
def recalculate_summary_analytics_task(self: LoggedTask) -> dict[str, Any]:
    ensure_worker_logging()
    return asyncio.run(_recalculate_summary_analytics())


async def _recalculate_summary_analytics(
    *,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> dict[str, Any]:
    from app.database.session import get_session_factory

    settings = get_settings()
    since = datetime.now(UTC) - timedelta(hours=24)

    factory = session_factory or get_session_factory()
    async with factory() as session:
        total_logs = int((await session.scalar(select(func.count(Log.id)))) or 0)

        last_24h = int(
            (await session.scalar(select(func.count()).where(Log.timestamp >= since))) or 0
        )

        by_service_rows = await session.execute(
            select(Log.service_name, func.count(Log.id))
            .where(Log.timestamp >= since)
            .group_by(Log.service_name)
        )
        by_environment_rows = await session.execute(
            select(Log.environment, func.count(Log.id))
            .where(Log.timestamp >= since)
            .group_by(Log.environment)
        )
        by_severity_rows = await session.execute(
            select(Log.log_level, func.count(Log.id))
            .where(Log.timestamp >= since)
            .group_by(Log.log_level)
        )

        unresolved_groups = int(
            (
                await session.scalar(
                    select(func.count()).where(ErrorGroup.status == ErrorGroupStatus.UNRESOLVED)
                )
            )
            or 0
        )

        frequent_groups_rows = await session.execute(
            select(ErrorGroup.id, ErrorGroup.title, ErrorGroup.occurrence_count)
            .order_by(ErrorGroup.occurrence_count.desc(), ErrorGroup.id.asc())
            .limit(10)
        )

        avg_occurrences = float(
            (await session.scalar(select(func.coalesce(func.avg(ErrorGroup.occurrence_count), 0))))
            or 0.0
        )

    payload: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "total_logs": total_logs,
        "logs_last_24h": last_24h,
        "logs_by_service": {name: int(count) for name, count in by_service_rows.all()},
        "logs_by_environment": {env.value: int(count) for env, count in by_environment_rows.all()},
        "logs_by_severity": {lvl.value: int(count) for lvl, count in by_severity_rows.all()},
        "unresolved_error_count": unresolved_groups,
        "most_frequent_error_groups": [
            {"group_id": gid, "title": title, "occurrence_count": int(count)}
            for gid, title, count in frequent_groups_rows.all()
        ],
        "avg_occurrences_per_group": avg_occurrences,
    }

    redis = get_redis_client()
    await redis.set(
        _ANALYTICS_CACHE_KEY, json.dumps(payload), ex=settings.analytics_cache_ttl_seconds
    )
    logger.info("Analytics cache refreshed", key=_ANALYTICS_CACHE_KEY)
    return payload
