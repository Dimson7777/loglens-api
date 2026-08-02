from __future__ import annotations

from datetime import datetime
from typing import cast

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.refresh_token import RefreshToken


class RefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_token(
        self,
        *,
        user_id: int,
        jti_hash: str,
        family_id: str,
        expires_at: datetime,
    ) -> RefreshToken:
        token = RefreshToken(
            user_id=user_id,
            jti_hash=jti_hash,
            family_id=family_id,
            expires_at=expires_at,
        )
        self._session.add(token)
        await self._session.flush()
        await self._session.refresh(token)
        return token

    async def get_by_jti_hash(self, jti_hash: str) -> RefreshToken | None:
        stmt = select(RefreshToken).where(RefreshToken.jti_hash == jti_hash)
        return cast(RefreshToken | None, await self._session.scalar(stmt))

    async def revoke_token(
        self,
        *,
        token: RefreshToken,
        revoked_at: datetime,
        replaced_by_jti_hash: str | None = None,
        mark_reuse: bool = False,
    ) -> None:
        token.revoked_at = revoked_at
        token.replaced_by_jti_hash = replaced_by_jti_hash
        if mark_reuse:
            token.reuse_detected_at = revoked_at
        await self._session.flush()

    async def revoke_family(
        self,
        *,
        family_id: str,
        revoked_at: datetime,
        mark_reuse: bool,
    ) -> None:
        values: dict[str, datetime] = {"revoked_at": revoked_at}
        if mark_reuse:
            values["reuse_detected_at"] = revoked_at

        stmt = (
            update(RefreshToken)
            .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
            .values(**values)
        )
        await self._session.execute(stmt)
        await self._session.flush()

    async def revoke_all_for_user(self, *, user_id: int, revoked_at: datetime) -> None:
        stmt = (
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=revoked_at)
        )
        await self._session.execute(stmt)
        await self._session.flush()
