from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.enums import LogEnvironment, LogLevel
from app.models.error_group import ErrorGroup
from app.models.log import Log


class LogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, log_id: int) -> Log | None:
        return await self._session.get(Log, log_id)

    async def create_log(self, **values: Any) -> Log:
        log = Log(**values)
        self._session.add(log)
        await self._session.flush()
        await self._session.refresh(log)
        return log

    async def delete_log(self, *, log: Log) -> None:
        await self._session.delete(log)
        await self._session.flush()

    def build_query(
        self,
        *,
        service: str | None = None,
        environment: LogEnvironment | None = None,
        level: LogLevel | None = None,
        fingerprint: str | None = None,
        error_group_id: int | None = None,
        text: str | None = None,
        from_timestamp: datetime | None = None,
        to_timestamp: datetime | None = None,
    ) -> Select[tuple[Log]]:
        group_alias = aliased(ErrorGroup)
        stmt: Select[tuple[Log]] = select(Log).outerjoin(
            group_alias,
            Log.error_group_id == group_alias.id,
        )
        conditions: list[Any] = []
        if service is not None:
            conditions.append(Log.service_name == service)
        if environment is not None:
            conditions.append(Log.environment == environment)
        if level is not None:
            conditions.append(Log.log_level == level)
        if fingerprint is not None:
            conditions.append(Log.fingerprint == fingerprint)
        if error_group_id is not None:
            conditions.append(Log.error_group_id == error_group_id)
        if from_timestamp is not None:
            conditions.append(Log.timestamp >= from_timestamp)
        if to_timestamp is not None:
            conditions.append(Log.timestamp <= to_timestamp)
        if text is not None:
            pattern = f"%{text.strip()}%"
            conditions.append(
                or_(
                    Log.message.ilike(pattern),
                    Log.normalized_message.ilike(pattern),
                    Log.stack_trace.ilike(pattern),
                    Log.fingerprint.ilike(pattern),
                    group_alias.title.ilike(pattern),
                    group_alias.fingerprint.ilike(pattern),
                )
            )
        if conditions:
            stmt = stmt.where(and_(*conditions))
        return stmt

    async def count_logs(self, stmt: Select[tuple[Log]]) -> int:
        count_stmt = select(func.count()).select_from(stmt.subquery())
        return cast(int, await self._session.scalar(count_stmt))

    async def list_logs(self, stmt: Select[tuple[Log]]) -> list[Log]:
        result = await self._session.scalars(stmt)
        return list(result)
