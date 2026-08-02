from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.user import User, UserRole
from app.repositories.user import UserRepository


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._user_repo = UserRepository(session)

    async def list_users(self) -> list[User]:
        return await self._user_repo.list_users()

    async def get_user_by_id(self, user_id: int) -> User:
        user = await self._user_repo.get_by_id(user_id)
        if user is None:
            raise NotFoundError(resource_name="User")
        return user

    async def update_user_role(self, *, user_id: int, role: UserRole) -> User:
        user = await self._user_repo.get_by_id(user_id)
        if user is None:
            raise NotFoundError(resource_name="User")

        updated_user = await self._user_repo.update_role(user=user, role=role)
        await self._session.commit()
        return updated_user

    async def update_user_status(self, *, user_id: int, is_active: bool) -> User:
        user = await self._user_repo.get_by_id(user_id)
        if user is None:
            raise NotFoundError(resource_name="User")

        updated_user = await self._user_repo.update_status(user=user, is_active=is_active)
        await self._session.commit()
        return updated_user
