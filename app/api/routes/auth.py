from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import ValidationError

from app.api.dependencies.auth import (
    build_login_rate_limit_key,
    get_auth_service,
    require_authenticated_user,
)
from app.core.exceptions import AuthenticationError
from app.models.user import User
from app.schemas.auth import (
    AuthenticatedUserResponse,
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    OAuth2TokenResponse,
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
    "/token",
    response_model=OAuth2TokenResponse,
    responses={401: {"model": ErrorEnvelope}, 429: {"model": ErrorEnvelope}},
    summary="OAuth2 password-flow login (Swagger Authorize)",
)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    request: Request,
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> OAuth2TokenResponse:
    """Form-encoded login for OAuth2 clients. Send the account email as `username`.

    Delegates to the same service and rate limiting as the JSON `/login` endpoint;
    only the request encoding and the flat response shape differ.
    """
    try:
        credentials = LoginRequest(email=form_data.username, password=form_data.password)
    except ValidationError:
        # A malformed email or an under-length password cannot match any account,
        # so report it as an ordinary credential failure rather than a 422.
        raise AuthenticationError() from None

    token = await auth_service.login_user(
        credentials,
        rate_limit_key=build_login_rate_limit_key(request=request, email=credentials.email),
    )
    return OAuth2TokenResponse(
        access_token=token.access_token,
        token_type=token.token_type,
        expires_in=token.expires_in_seconds,
        refresh_token=token.refresh_token,
    )


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
