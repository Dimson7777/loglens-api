from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, cast

from httpx import AsyncClient

from app.models.user import User, UserRole


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _login(async_client: AsyncClient, *, email: str, password: str) -> str:
    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    payload = cast(dict[str, Any], response.json())
    return str(cast(dict[str, Any], payload["token"])["access_token"])


async def test_admin_can_update_status_and_assignment(
    async_client: AsyncClient,
    user_factory: Callable[..., Awaitable[User]],
) -> None:
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": "groupdev@example.com", "password": "supersecurepass"},
    )
    token = await _login(async_client, email="groupdev@example.com", password="supersecurepass")

    log_response = await async_client.post(
        "/api/v1/logs",
        headers=_auth_header(token),
        json={
            "service_name": "api-service",
            "environment": "production",
            "log_level": "error",
            "message": "Unhandled error 1",
            "exception_type": "RuntimeError",
            "stack_trace": 'File "/app/app/services/x.py", line 10, in run',
            "metadata": {},
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )
    group_id = cast(dict[str, Any], log_response.json())["error_group_id"]

    await user_factory(
        email="groupadmin@example.com",
        password="supersecurepass",
        role=UserRole.ADMIN,
    )
    admin_token = await _login(
        async_client,
        email="groupadmin@example.com",
        password="supersecurepass",
    )

    status_response = await async_client.patch(
        f"/api/v1/error-groups/{group_id}/status",
        headers=_auth_header(admin_token),
        json={"status": "investigating"},
    )
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "investigating"

    assignment_response = await async_client.patch(
        f"/api/v1/error-groups/{group_id}/assignment",
        headers=_auth_header(admin_token),
        json={"assigned_to": 1},
    )
    assert assignment_response.status_code == 200
    assert assignment_response.json()["assigned_to"] == 1


async def test_developer_assignment_policy_blocks_other_users(
    async_client: AsyncClient,
    user_factory: Callable[..., Awaitable[User]],
) -> None:
    group_user = await user_factory(
        email="assigndev@example.com",
        password="supersecurepass",
        role=UserRole.DEVELOPER,
    )
    await user_factory(
        email="otherdev@example.com",
        password="supersecurepass",
        role=UserRole.DEVELOPER,
    )
    token = await _login(async_client, email="assigndev@example.com", password="supersecurepass")

    log_response = await async_client.post(
        "/api/v1/logs",
        headers=_auth_header(token),
        json={
            "service_name": "api-service",
            "environment": "production",
            "log_level": "error",
            "message": "Unhandled error 2",
            "exception_type": "RuntimeError",
            "stack_trace": 'File "/app/app/services/x.py", line 10, in run',
            "metadata": {},
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )
    group_id = cast(dict[str, Any], log_response.json())["error_group_id"]

    response = await async_client.patch(
        f"/api/v1/error-groups/{group_id}/assignment",
        headers=_auth_header(token),
        json={"assigned_to": group_user.id + 1},
    )
    assert response.status_code == 403


async def test_error_group_filtering_and_pagination(async_client: AsyncClient) -> None:
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": "filtergroup@example.com", "password": "supersecurepass"},
    )
    token = await _login(async_client, email="filtergroup@example.com", password="supersecurepass")

    for index in range(3):
        await async_client.post(
            "/api/v1/logs",
            headers=_auth_header(token),
            json={
                "service_name": "filter-api",
                "environment": "production",
                "log_level": "error",
                "message": f"Filterable error {index}",
                "exception_type": "ValueError",
                "stack_trace": 'File "/app/app/services/x.py", line 10, in run',
                "metadata": {},
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

    response = await async_client.get(
        "/api/v1/error-groups?page=1&page_size=1&service=filter-api&sort_by=occurrence_count&sort_order=desc",
        headers=_auth_header(token),
    )

    body = response.json()
    assert body["pagination"]["total_items"] == 3
    assert len(body["items"]) == 1


async def test_error_group_analysis_endpoints(async_client: AsyncClient) -> None:
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": "analysisdev@example.com", "password": "supersecurepass"},
    )
    token = await _login(async_client, email="analysisdev@example.com", password="supersecurepass")

    log_response = await async_client.post(
        "/api/v1/logs",
        headers=_auth_header(token),
        json={
            "service_name": "analysis-api",
            "environment": "production",
            "log_level": "error",
            "message": "database connection timeout",
            "exception_type": "TimeoutError",
            "stack_trace": 'File "/app/db.py", line 11, in connect',
            "metadata": {},
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )
    group_id = log_response.json()["error_group_id"]

    analyze_response = await async_client.post(
        f"/api/v1/error-groups/{group_id}/analyze",
        headers=_auth_header(token),
    )
    assert analyze_response.status_code == 202

    latest_response = await async_client.get(
        f"/api/v1/error-groups/{group_id}/analysis",
        headers=_auth_header(token),
    )
    assert latest_response.status_code == 200
    latest = latest_response.json()
    assert latest["error_group_id"] == group_id
    assert latest["status"] in {"completed", "failed"}

    history_response = await async_client.get(
        f"/api/v1/error-groups/{group_id}/analyses",
        headers=_auth_header(token),
    )
    assert history_response.status_code == 200
    history = history_response.json()
    assert len(history) >= 1


async def test_error_group_analysis_requires_auth(async_client: AsyncClient) -> None:
    response = await async_client.post("/api/v1/error-groups/1/analyze")
    assert response.status_code == 401
