from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, cast

from httpx import AsyncClient

from app.api.dependencies.auth import require_developer_or_admin
from app.models.user import User, UserRole


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _register_and_login(
    async_client: AsyncClient,
    *,
    email: str,
    password: str,
) -> str:
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
    )
    login_response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    payload = cast(dict[str, Any], login_response.json())
    token_payload = cast(dict[str, Any], payload["token"])
    return str(token_payload["access_token"])


async def test_admin_authorization_required_for_list_users(
    async_client: AsyncClient,
) -> None:
    token = await _register_and_login(
        async_client,
        email="devlist@example.com",
        password="supersecurepass",
    )

    response = await async_client.get("/api/v1/users", headers=_auth_header(token))
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


async def test_admin_can_list_users(
    async_client: AsyncClient,
    user_factory: Callable[..., Awaitable[User]],
) -> None:
    await user_factory(
        email="adminlist@example.com",
        password="supersecurepass",
        role=UserRole.ADMIN,
    )

    login_response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "adminlist@example.com", "password": "supersecurepass"},
    )
    token = login_response.json()["token"]["access_token"]

    response = await async_client.get("/api/v1/users", headers=_auth_header(token))
    assert response.status_code == 200
    assert any(user["email"] == "adminlist@example.com" for user in response.json())


async def test_admin_can_update_user_role(
    async_client: AsyncClient,
    user_factory: Callable[..., Awaitable[User]],
) -> None:
    target = await user_factory(
        email="targetrole@example.com",
        password="supersecurepass",
        role=UserRole.DEVELOPER,
    )
    await user_factory(
        email="adminrole@example.com",
        password="supersecurepass",
        role=UserRole.ADMIN,
    )

    login_response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "adminrole@example.com", "password": "supersecurepass"},
    )
    token = login_response.json()["token"]["access_token"]

    response = await async_client.patch(
        f"/api/v1/users/{target.id}/role",
        headers=_auth_header(token),
        json={"role": "admin"},
    )

    assert response.status_code == 200
    assert response.json()["role"] == "admin"


async def test_admin_can_update_user_status(
    async_client: AsyncClient,
    user_factory: Callable[..., Awaitable[User]],
) -> None:
    target = await user_factory(
        email="targetstatus@example.com",
        password="supersecurepass",
        role=UserRole.DEVELOPER,
    )
    await user_factory(
        email="adminstatus@example.com",
        password="supersecurepass",
        role=UserRole.ADMIN,
    )

    login_response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "adminstatus@example.com", "password": "supersecurepass"},
    )
    token = login_response.json()["token"]["access_token"]

    response = await async_client.patch(
        f"/api/v1/users/{target.id}/status",
        headers=_auth_header(token),
        json={"is_active": False},
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False


async def test_developer_or_admin_dependency_allows_developer_and_admin() -> None:
    developer = User(
        id=1,
        email="dep-dev@example.com",
        password_hash="hash",
        role=UserRole.DEVELOPER,
        is_active=True,
    )
    admin = User(
        id=2,
        email="dep-admin@example.com",
        password_hash="hash",
        role=UserRole.ADMIN,
        is_active=True,
    )

    developer_result = await require_developer_or_admin(developer)
    admin_result = await require_developer_or_admin(admin)

    assert developer_result.role == UserRole.DEVELOPER
    assert admin_result.role == UserRole.ADMIN
