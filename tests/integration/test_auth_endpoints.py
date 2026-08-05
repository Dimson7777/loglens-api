from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, cast

from httpx import AsyncClient

from app.models.user import User, UserRole


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _token_payload(response_json: dict[str, Any]) -> dict[str, Any]:
    return cast(dict[str, Any], response_json["token"])


async def test_registration_success(async_client: AsyncClient) -> None:
    response = await async_client.post(
        "/api/v1/auth/register",
        json={"email": "dev1@example.com", "password": "supersecurepass"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["email"] == "dev1@example.com"
    assert payload["role"] == UserRole.DEVELOPER.value
    assert "password_hash" not in payload


async def test_duplicate_email_registration(async_client: AsyncClient) -> None:
    body = {"email": "dupe@example.com", "password": "supersecurepass"}
    first_response = await async_client.post("/api/v1/auth/register", json=body)
    second_response = await async_client.post("/api/v1/auth/register", json=body)

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.json()["error"]["code"] == "email_already_registered"


async def test_login_success_and_me(async_client: AsyncClient) -> None:
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": "authme@example.com", "password": "supersecurepass"},
    )

    login_response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "authme@example.com", "password": "supersecurepass"},
    )
    assert login_response.status_code == 200

    token_payload = _token_payload(cast(dict[str, Any], login_response.json()))
    token = str(token_payload["access_token"])
    assert "refresh_token" in token_payload

    me_response = await async_client.get("/api/v1/auth/me", headers=_auth_header(token))

    assert me_response.status_code == 200
    me_payload = me_response.json()
    assert me_payload["email"] == "authme@example.com"
    assert me_payload["role"] == UserRole.DEVELOPER.value


async def test_invalid_password_login(async_client: AsyncClient) -> None:
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": "invalidpass@example.com", "password": "supersecurepass"},
    )

    bad_login_response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "invalidpass@example.com", "password": "wrongpassword"},
    )

    assert bad_login_response.status_code == 401
    assert bad_login_response.json()["error"]["code"] == "authentication_failed"


async def test_oauth2_token_form_login_success_and_me(async_client: AsyncClient) -> None:
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": "swagger@example.com", "password": "supersecurepass"},
    )

    token_response = await async_client.post(
        "/api/v1/auth/token",
        data={"username": "swagger@example.com", "password": "supersecurepass"},
    )
    assert token_response.status_code == 200
    assert token_response.request.headers["content-type"] == "application/x-www-form-urlencoded"

    payload = token_response.json()
    assert payload["token_type"] == "bearer"
    assert isinstance(payload["access_token"], str)
    assert payload["access_token"]
    assert payload["expires_in"] > 0

    me_response = await async_client.get(
        "/api/v1/auth/me",
        headers=_auth_header(str(payload["access_token"])),
    )

    assert me_response.status_code == 200
    assert me_response.json()["email"] == "swagger@example.com"


async def test_oauth2_token_form_login_rejects_invalid_password(async_client: AsyncClient) -> None:
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": "swaggerbad@example.com", "password": "supersecurepass"},
    )

    response = await async_client.post(
        "/api/v1/auth/token",
        data={"username": "swaggerbad@example.com", "password": "wrongpassword"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_failed"


async def test_oauth2_token_form_login_rejects_unknown_email(async_client: AsyncClient) -> None:
    response = await async_client.post(
        "/api/v1/auth/token",
        data={"username": "nobody@example.com", "password": "supersecurepass"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_failed"


async def test_oauth2_token_form_rejects_malformed_username(async_client: AsyncClient) -> None:
    """A non-email username or short password is a credential failure, not a 500."""
    malformed_username = await async_client.post(
        "/api/v1/auth/token",
        data={"username": "not-an-email", "password": "supersecurepass"},
    )
    short_password = await async_client.post(
        "/api/v1/auth/token",
        data={"username": "swaggershort@example.com", "password": "short"},
    )

    assert malformed_username.status_code == 401
    assert malformed_username.json()["error"]["code"] == "authentication_failed"
    assert short_password.status_code == 401
    assert short_password.json()["error"]["code"] == "authentication_failed"


async def test_oauth2_token_form_login_respects_inactive_user(
    async_client: AsyncClient,
    user_factory: Callable[..., Awaitable[User]],
) -> None:
    await user_factory(
        email="swaggerinactive@example.com",
        password="supersecurepass",
        role=UserRole.DEVELOPER,
        is_active=False,
    )

    response = await async_client.post(
        "/api/v1/auth/token",
        data={"username": "swaggerinactive@example.com", "password": "supersecurepass"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "inactive_user"


async def test_inactive_user_login(
    async_client: AsyncClient,
    user_factory: Callable[..., Awaitable[User]],
) -> None:
    await user_factory(
        email="inactive@example.com",
        password="supersecurepass",
        role=UserRole.DEVELOPER,
        is_active=False,
    )

    login_response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "inactive@example.com", "password": "supersecurepass"},
    )

    assert login_response.status_code == 403
    assert login_response.json()["error"]["code"] == "inactive_user"


async def test_refresh_rotates_and_reuse_revokes_family(async_client: AsyncClient) -> None:
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": "refresh@example.com", "password": "supersecurepass"},
    )

    login_response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "refresh@example.com", "password": "supersecurepass"},
    )
    first_token_payload = _token_payload(cast(dict[str, Any], login_response.json()))
    first_refresh = str(first_token_payload["refresh_token"])

    refresh_response = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": first_refresh},
    )
    assert refresh_response.status_code == 200
    second_token_payload = _token_payload(cast(dict[str, Any], refresh_response.json()))
    second_refresh = str(second_token_payload["refresh_token"])
    assert second_refresh != first_refresh

    reused_old_token_response = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": first_refresh},
    )
    assert reused_old_token_response.status_code == 401

    second_refresh_after_reuse_response = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": second_refresh},
    )
    assert second_refresh_after_reuse_response.status_code == 401


async def test_logout_revokes_refresh_token(async_client: AsyncClient) -> None:
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": "logout@example.com", "password": "supersecurepass"},
    )
    login_response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "logout@example.com", "password": "supersecurepass"},
    )
    token_payload = _token_payload(cast(dict[str, Any], login_response.json()))
    refresh_token = str(token_payload["refresh_token"])

    logout_response = await async_client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
    )
    assert logout_response.status_code == 200

    refresh_response = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_response.status_code == 401


async def test_logout_all_revokes_all_user_refresh_tokens(async_client: AsyncClient) -> None:
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": "logoutall@example.com", "password": "supersecurepass"},
    )
    first_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "logoutall@example.com", "password": "supersecurepass"},
    )
    first_tokens = _token_payload(cast(dict[str, Any], first_login.json()))

    second_login = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "logoutall@example.com", "password": "supersecurepass"},
    )
    second_tokens = _token_payload(cast(dict[str, Any], second_login.json()))

    logout_all_response = await async_client.post(
        "/api/v1/auth/logout-all",
        headers=_auth_header(str(first_tokens["access_token"])),
    )
    assert logout_all_response.status_code == 200

    first_refresh_after_logout_all = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": str(first_tokens["refresh_token"])},
    )
    second_refresh_after_logout_all = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": str(second_tokens["refresh_token"])},
    )
    assert first_refresh_after_logout_all.status_code == 401
    assert second_refresh_after_logout_all.status_code == 401


async def test_login_rate_limit_blocks_after_max_attempts(async_client: AsyncClient) -> None:
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": "ratelimit@example.com", "password": "supersecurepass"},
    )

    for _ in range(5):
        response = await async_client.post(
            "/api/v1/auth/login",
            json={"email": "ratelimit@example.com", "password": "wrongpassword"},
        )
        assert response.status_code == 401

    blocked_response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "ratelimit@example.com", "password": "wrongpassword"},
    )
    assert blocked_response.status_code == 429
