from __future__ import annotations

from math import ceil

from sqlalchemy import desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, NotFoundError
from app.models.error_group import ErrorGroup
from app.models.user import User, UserRole
from app.repositories.error_group import ErrorGroupRepository
from app.repositories.user import UserRepository
from app.schemas.common import PaginationMeta
from app.schemas.error_group import (
    ErrorGroupAssignmentUpdateRequest,
    ErrorGroupListQuery,
    ErrorGroupListResponse,
    ErrorGroupResponse,
    ErrorGroupStatusUpdateRequest,
)


class ErrorGroupService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._group_repo = ErrorGroupRepository(session)
        self._user_repo = UserRepository(session)

    async def get_error_group(self, group_id: int) -> ErrorGroup:
        group = await self._group_repo.get_by_id(group_id)
        if group is None:
            raise NotFoundError(resource_name="ErrorGroup")
        return group

    async def list_error_groups(self, query: ErrorGroupListQuery) -> ErrorGroupListResponse:
        stmt = self._group_repo.build_query(
            service=query.service,
            environment=query.environment,
            status=query.status,
            severity=query.severity,
            assigned_to=query.assigned_to,
            text=query.text,
            from_timestamp=query.from_timestamp,
            to_timestamp=query.to_timestamp,
        )
        column_map = {
            "last_seen": ErrorGroup.last_seen,
            "occurrence_count": ErrorGroup.occurrence_count,
            "created_at": ErrorGroup.created_at,
        }
        column = column_map[query.sort_by]
        if query.sort_order == "asc":
            stmt = stmt.order_by(column.asc(), ErrorGroup.id.asc())
        else:
            stmt = stmt.order_by(desc(column), ErrorGroup.id.desc())
        total_items = await self._group_repo.count_groups(stmt)
        offset = (query.page - 1) * query.page_size
        stmt = stmt.limit(query.page_size).offset(offset)
        groups = await self._group_repo.list_groups(stmt)
        total_pages = ceil(total_items / query.page_size) if total_items else 0
        return ErrorGroupListResponse(
            items=[ErrorGroupResponse.model_validate(group) for group in groups],
            pagination=PaginationMeta(
                page=query.page,
                page_size=query.page_size,
                total_items=total_items,
                total_pages=total_pages,
            ),
        )

    async def update_status(
        self,
        *,
        group_id: int,
        payload: ErrorGroupStatusUpdateRequest,
    ) -> ErrorGroup:
        group = await self.get_error_group(group_id)
        updated_group = await self._group_repo.update_status(group=group, status=payload.status)
        await self._session.commit()
        return updated_group

    async def update_assignment(
        self,
        *,
        group_id: int,
        payload: ErrorGroupAssignmentUpdateRequest,
        current_user: User,
    ) -> ErrorGroup:
        group = await self.get_error_group(group_id)

        if current_user.role == UserRole.DEVELOPER and payload.assigned_to not in {
            None,
            current_user.id,
        }:
            raise AuthorizationError(
                message="Developers may only assign error groups to themselves."
            )

        if payload.assigned_to is not None:
            assignee = await self._user_repo.get_by_id(payload.assigned_to)
            if assignee is None:
                raise NotFoundError(resource_name="User")

        updated_group = await self._group_repo.update_assignment(
            group=group,
            assigned_to=payload.assigned_to,
        )
        await self._session.commit()
        return updated_group
