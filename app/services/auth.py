from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AuthenticationError,
    DuplicateEmailError,
    InactiveUserError,
    RateLimitExceededError,
)
from app.core.rate_limit import LoginRateLimiter
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    hash_refresh_token_identifier,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.repositories.refresh_token import RefreshTokenRepository
from app.repositories.user import UserRepository
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse


def _as_utc_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class AuthService:
    def __init__(self, session: AsyncSession, rate_limiter: LoginRateLimiter) -> None:
        self._session = session
        self._user_repo = UserRepository(session)
        self._refresh_token_repo = RefreshTokenRepository(session)
        self._rate_limiter = rate_limiter

    async def _issue_token_pair(self, *, user: User, family_id: str | None = None) -> TokenResponse:
        access_token, access_expires_in_seconds = create_access_token(subject=str(user.id))
        refresh = create_refresh_token(subject=str(user.id), family_id=family_id)

        await self._refresh_token_repo.create_token(
            user_id=user.id,
            jti_hash=hash_refresh_token_identifier(refresh.jti),
            family_id=refresh.family_id,
            expires_at=refresh.expires_at,
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh.token,
            token_type="bearer",
            expires_in_seconds=access_expires_in_seconds,
            refresh_expires_in_seconds=refresh.expires_in_seconds,
        )

    async def _get_refresh_token_record(
        self,
        *,
        refresh_token: str,
    ) -> tuple[RefreshToken, int, str]:
        try:
            payload = decode_refresh_token(refresh_token)
            user_id = int(payload["sub"])
        except (ValueError, TypeError):
            raise AuthenticationError() from None

        jti_hash = hash_refresh_token_identifier(payload["jti"])
        token_record = await self._refresh_token_repo.get_by_jti_hash(jti_hash)
        if token_record is None or token_record.user_id != user_id:
            raise AuthenticationError() from None

        return token_record, user_id, payload["family_id"]

    async def register_user(self, payload: RegisterRequest) -> User:
        normalized_email = payload.email.strip().lower()

        existing_user = await self._user_repo.get_by_email(normalized_email)
        if existing_user is not None:
            raise DuplicateEmailError()

        password_hash = hash_password(payload.password)
        try:
            user = await self._user_repo.create_user(
                email=normalized_email,
                password_hash=password_hash,
            )
        except IntegrityError as exc:
            await self._session.rollback()
            raise DuplicateEmailError() from exc

        await self._session.commit()
        return user

    async def login_user(self, payload: LoginRequest, *, rate_limit_key: str) -> TokenResponse:
        if not await self._rate_limiter.is_allowed(rate_limit_key):
            raise RateLimitExceededError()

        normalized_email = payload.email.strip().lower()
        user = await self._user_repo.get_by_email(normalized_email)

        if user is None or not verify_password(payload.password, user.password_hash):
            await self._rate_limiter.add_failure(rate_limit_key)
            raise AuthenticationError()

        if not user.is_active:
            raise InactiveUserError()

        await self._rate_limiter.clear(rate_limit_key)
        token_pair = await self._issue_token_pair(user=user)
        await self._session.commit()
        return token_pair

    async def refresh_session(self, payload: RefreshRequest) -> TokenResponse:
        token_record, user_id, family_id = await self._get_refresh_token_record(
            refresh_token=payload.refresh_token
        )

        now = datetime.now(UTC)
        if _as_utc_aware(token_record.expires_at) <= now:
            await self._refresh_token_repo.revoke_token(token=token_record, revoked_at=now)
            await self._session.commit()
            raise AuthenticationError() from None

        if token_record.revoked_at is not None:
            if token_record.replaced_by_jti_hash is not None:
                await self._refresh_token_repo.revoke_family(
                    family_id=token_record.family_id,
                    revoked_at=now,
                    mark_reuse=True,
                )
                await self._session.commit()
            raise AuthenticationError() from None

        user = await self._user_repo.get_by_id(user_id)
        if user is None or not user.is_active:
            raise AuthenticationError() from None

        next_refresh = create_refresh_token(subject=str(user.id), family_id=family_id)
        next_jti_hash = hash_refresh_token_identifier(next_refresh.jti)

        await self._refresh_token_repo.revoke_token(
            token=token_record,
            revoked_at=now,
            replaced_by_jti_hash=next_jti_hash,
        )

        await self._refresh_token_repo.create_token(
            user_id=user.id,
            jti_hash=next_jti_hash,
            family_id=family_id,
            expires_at=next_refresh.expires_at,
        )

        access_token, access_expires_in_seconds = create_access_token(subject=str(user.id))
        await self._session.commit()
        return TokenResponse(
            access_token=access_token,
            refresh_token=next_refresh.token,
            token_type="bearer",
            expires_in_seconds=access_expires_in_seconds,
            refresh_expires_in_seconds=next_refresh.expires_in_seconds,
        )

    async def logout(self, payload: RefreshRequest) -> None:
        token_record, _, _ = await self._get_refresh_token_record(
            refresh_token=payload.refresh_token
        )
        if token_record.revoked_at is None:
            await self._refresh_token_repo.revoke_token(
                token=token_record,
                revoked_at=datetime.now(UTC),
            )
            await self._session.commit()

    async def logout_all(self, *, user_id: int) -> None:
        await self._refresh_token_repo.revoke_all_for_user(
            user_id=user_id,
            revoked_at=datetime.now(UTC),
        )
        await self._session.commit()
