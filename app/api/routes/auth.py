from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from app.api.dependencies.auth import (
    build_login_rate_limit_key,
    get_auth_service,
    require_authenticated_user,
)
from app.models.user import User
from app.schemas.auth import (
    AuthenticatedUserResponse,
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    RefreshRequest,
    RegisterRequest,
)
from app.schemas.common import ErrorEnvelope
from app.schemas.users import UserResponse
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    responses={409: {"model": ErrorEnvelope}},
)
async def register(
    payload: RegisterRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> UserResponse:
    user = await auth_service.register_user(payload)
    return UserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=LoginResponse,
    responses={401: {"model": ErrorEnvelope}, 429: {"model": ErrorEnvelope}},
)
async def login(
    payload: LoginRequest,
    request: Request,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> LoginResponse:
    token = await auth_service.login_user(
        payload,
        rate_limit_key=build_login_rate_limit_key(request=request, email=payload.email),
    )
    return LoginResponse(token=token)


@router.post(
    "/refresh",
    response_model=LoginResponse,
    responses={401: {"model": ErrorEnvelope}},
)
async def refresh(
    payload: RefreshRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> LoginResponse:
    token = await auth_service.refresh_session(payload)
    return LoginResponse(token=token)


@router.post(
    "/logout",
    response_model=LogoutResponse,
    responses={401: {"model": ErrorEnvelope}},
)
async def logout(
    payload: RefreshRequest,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> LogoutResponse:
    await auth_service.logout(payload)
    return LogoutResponse()


@router.post(
    "/logout-all",
    response_model=LogoutResponse,
    responses={401: {"model": ErrorEnvelope}},
)
async def logout_all(
    current_user: Annotated[User, Depends(require_authenticated_user)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> LogoutResponse:
    await auth_service.logout_all(user_id=current_user.id)
    return LogoutResponse()


@router.get("/me", response_model=AuthenticatedUserResponse)
async def me(
    current_user: Annotated[User, Depends(require_authenticated_user)],
) -> AuthenticatedUserResponse:
    return AuthenticatedUserResponse.model_validate(current_user)
