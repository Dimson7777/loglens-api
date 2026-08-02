from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies.auth import get_user_service, require_admin_user
from app.models.user import User
from app.schemas.common import ErrorEnvelope
from app.schemas.users import UpdateUserRoleRequest, UpdateUserStatusRequest, UserResponse
from app.services.users import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserResponse])
async def list_users(
    _: Annotated[User, Depends(require_admin_user)],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> list[UserResponse]:
    users = await user_service.list_users()
    return [UserResponse.model_validate(user) for user in users]


@router.patch(
    "/{user_id}/role",
    response_model=UserResponse,
    responses={403: {"model": ErrorEnvelope}, 404: {"model": ErrorEnvelope}},
)
async def update_user_role(
    user_id: int,
    payload: UpdateUserRoleRequest,
    _: Annotated[User, Depends(require_admin_user)],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> UserResponse:
    user = await user_service.update_user_role(user_id=user_id, role=payload.role)
    return UserResponse.model_validate(user)


@router.patch(
    "/{user_id}/status",
    response_model=UserResponse,
    responses={403: {"model": ErrorEnvelope}, 404: {"model": ErrorEnvelope}},
)
async def update_user_status(
    user_id: int,
    payload: UpdateUserStatusRequest,
    _: Annotated[User, Depends(require_admin_user)],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> UserResponse:
    user = await user_service.update_user_status(user_id=user_id, is_active=payload.is_active)
    return UserResponse.model_validate(user)
