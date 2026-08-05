from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, AuthorizationError, NotFoundError
from app.core.rate_limit import LoginRateLimiter, get_login_rate_limiter
from app.core.security import decode_access_token
from app.database.session import get_db_session
from app.models.user import User, UserRole
from app.services.auth import AuthService
from app.services.users import UserService

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


def get_rate_limiter() -> LoginRateLimiter:
    return get_login_rate_limiter()


def get_auth_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    rate_limiter: Annotated[LoginRateLimiter, Depends(get_rate_limiter)],
) -> AuthService:
    return AuthService(session=session, rate_limiter=rate_limiter)


def get_user_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserService:
    return UserService(session=session)


async def get_current_user(
    token: Annotated[str, Depends(_oauth2_scheme)],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> User:
    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
    except (ValueError, TypeError):
        raise AuthenticationError() from None

    try:
        user = await user_service.get_user_by_id(user_id)
    except NotFoundError:
        raise AuthenticationError() from None

    if not user.is_active:
        raise AuthenticationError(message="Inactive user.")

    return user


async def require_authenticated_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    return current_user


async def require_admin_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if current_user.role != UserRole.ADMIN:
        raise AuthorizationError(message="Admin privileges required.")
    return current_user


async def require_developer_or_admin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    if current_user.role not in {UserRole.ADMIN, UserRole.DEVELOPER}:
        raise AuthorizationError(message="Developer or admin privileges required.")
    return current_user


def build_login_rate_limit_key(*, request: Request, email: str) -> str:
    client_host = request.client.host if request.client is not None else "unknown"
    return f"{client_host}:{email.strip().lower()}"
