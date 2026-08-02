from __future__ import annotations

from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: int) -> User | None:
        return await self._session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        return cast(User | None, await self._session.scalar(stmt))

    async def create_user(
        self,
        *,
        email: str,
        password_hash: str,
        role: UserRole = UserRole.DEVELOPER,
        is_active: bool = True,
    ) -> User:
        user = User(
            email=email,
            password_hash=password_hash,
            role=role,
            is_active=is_active,
        )
        self._session.add(user)
        await self._session.flush()
        await self._session.refresh(user)
        return user

    async def list_users(self) -> list[User]:
        stmt = select(User).order_by(User.id.asc())
        result = await self._session.scalars(stmt)
        return list(result)

    async def update_role(self, *, user: User, role: UserRole) -> User:
        user.role = role
        await self._session.flush()
        await self._session.refresh(user)
        return user

    async def update_status(self, *, user: User, is_active: bool) -> User:
        user.is_active = is_active
        await self._session.flush()
        await self._session.refresh(user)
        return user
