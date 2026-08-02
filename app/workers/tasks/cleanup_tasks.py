from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import structlog
from celery import shared_task
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.models.log import Log
from app.workers.tasks._common import LoggedTask, ensure_worker_logging

logger = structlog.get_logger(__name__)


@shared_task(bind=True, base=LoggedTask)  # type: ignore[untyped-decorator]
def cleanup_old_logs_task(self: LoggedTask, dry_run: bool | None = None) -> dict[str, int | bool]:
    ensure_worker_logging()
    return asyncio.run(_cleanup_old_logs(dry_run=dry_run))


async def _cleanup_old_logs(
    *,
    dry_run: bool | None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> dict[str, int | bool]:
    from app.database.session import get_session_factory

    settings = get_settings()
    run_dry = settings.cleanup_dry_run_default if dry_run is None else dry_run
    threshold = datetime.now(UTC) - timedelta(days=settings.log_retention_days)

    deleted = 0
    factory = session_factory or get_session_factory()
    async with factory() as session:
        if run_dry:
            deleted = int(
                (await session.scalar(select(func.count()).where(Log.timestamp < threshold))) or 0
            )
            logger.info(
                "Cleanup task dry run completed",
                dry_run=True,
                candidate_count=deleted,
                retention_days=settings.log_retention_days,
            )
            return {"dry_run": True, "deleted_count": deleted}

        while True:
            ids = list(
                await session.scalars(
                    select(Log.id)
                    .where(Log.timestamp < threshold)
                    .order_by(Log.id.asc())
                    .limit(settings.cleanup_batch_size)
                )
            )
            if not ids:
                break

            await session.execute(delete(Log).where(Log.id.in_(ids)))
            await session.commit()
            deleted += len(ids)

    logger.info(
        "Cleanup task completed",
        dry_run=run_dry,
        deleted_count=deleted,
        retention_days=settings.log_retention_days,
    )
    return {"dry_run": run_dry, "deleted_count": deleted}
