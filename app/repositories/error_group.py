from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ErrorGroupSeverity, ErrorGroupStatus, LogEnvironment
from app.models.error_group import ErrorGroup


class ErrorGroupRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, group_id: int) -> ErrorGroup | None:
        return await self._session.get(ErrorGroup, group_id)

    async def upsert_group(
        self,
        *,
        fingerprint: str,
        title: str,
        service_name: str,
        environment: LogEnvironment,
        exception_type: str | None,
        first_seen: datetime,
        last_seen: datetime,
        severity: ErrorGroupSeverity,
    ) -> ErrorGroup:
        stmt: Any = pg_insert(ErrorGroup).values(
            fingerprint=fingerprint,
            title=title,
            service_name=service_name,
            environment=environment,
            exception_type=exception_type,
            first_seen=first_seen,
            last_seen=last_seen,
            severity=severity,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                ErrorGroup.service_name,
                ErrorGroup.environment,
                ErrorGroup.fingerprint,
            ],
            set_={
                "title": stmt.excluded.title,
                "exception_type": stmt.excluded.exception_type,
                "last_seen": stmt.excluded.last_seen,
                "severity": stmt.excluded.severity,
                "updated_at": func.now(),
                "occurrence_count": ErrorGroup.occurrence_count + 1,
            },
        ).returning(ErrorGroup.id)
        result = await self._session.execute(stmt)
        group_id = result.scalar_one()
        group = await self._session.get(ErrorGroup, group_id)
        assert group is not None
        return group

    async def update_status(self, *, group: ErrorGroup, status: ErrorGroupStatus) -> ErrorGroup:
        group.status = status
        await self._session.flush()
        await self._session.refresh(group)
        return group

    async def update_assignment(self, *, group: ErrorGroup, assigned_to: int | None) -> ErrorGroup:
        group.assigned_to = assigned_to
        await self._session.flush()
        await self._session.refresh(group)
        return group

    def build_query(
        self,
        *,
        service: str | None = None,
        environment: LogEnvironment | None = None,
        status: ErrorGroupStatus | None = None,
        severity: ErrorGroupSeverity | None = None,
        assigned_to: int | None = None,
        text: str | None = None,
        from_timestamp: datetime | None = None,
        to_timestamp: datetime | None = None,
    ) -> Select[tuple[ErrorGroup]]:
        stmt: Select[tuple[ErrorGroup]] = select(ErrorGroup)
        conditions: list[Any] = []
        if service is not None:
            conditions.append(ErrorGroup.service_name == service)
        if environment is not None:
            conditions.append(ErrorGroup.environment == environment)
        if status is not None:
            conditions.append(ErrorGroup.status == status)
        if severity is not None:
            conditions.append(ErrorGroup.severity == severity)
        if assigned_to is not None:
            conditions.append(ErrorGroup.assigned_to == assigned_to)
        if from_timestamp is not None:
            conditions.append(ErrorGroup.last_seen >= from_timestamp)
        if to_timestamp is not None:
            conditions.append(ErrorGroup.first_seen <= to_timestamp)
        if text is not None:
            pattern = f"%{text.strip()}%"
            conditions.append(
                or_(
                    ErrorGroup.title.ilike(pattern),
                    ErrorGroup.fingerprint.ilike(pattern),
                    ErrorGroup.exception_type.ilike(pattern),
                    ErrorGroup.service_name.ilike(pattern),
                )
            )
        if conditions:
            stmt = stmt.where(and_(*conditions))
        return stmt

    async def count_groups(self, stmt: Select[tuple[ErrorGroup]]) -> int:
        count_stmt = select(func.count()).select_from(stmt.subquery())
        return cast(int, await self._session.scalar(count_stmt))

    async def list_groups(self, stmt: Select[tuple[ErrorGroup]]) -> list[ErrorGroup]:
        result = await self._session.scalars(stmt)
        return list(result)
