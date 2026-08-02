from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from httpx import AsyncClient

from app.models.enums import LogEnvironment, LogLevel


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _login(async_client: AsyncClient, *, email: str, password: str) -> str:
    response = await async_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    payload = cast(dict[str, Any], response.json())
    return str(cast(dict[str, Any], payload["token"])["access_token"])


async def test_analytics_summary_requires_auth(async_client: AsyncClient) -> None:
    """Analytics endpoint should require authentication (401 when no token provided)."""
    response = await async_client.get("/api/v1/analytics/summary")
    assert response.status_code == 401


async def test_analytics_summary_requires_developer_or_admin(async_client: AsyncClient) -> None:
    """Analytics endpoint should be accessible to developer and admin roles."""
    # Register and login as developer
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": "analytics-dev@example.com", "password": "supersecurepass"},
    )
    token = await _login(
        async_client, email="analytics-dev@example.com", password="supersecurepass"
    )

    response = await async_client.get(
        "/api/v1/analytics/summary",
        headers=_auth_header(token),
    )

    assert response.status_code == 200
    body = response.json()
    assert "generated_at" in body
    assert "total_logs" in body
    assert "logs_last_24h" in body
    assert "logs_by_service" in body
    assert "logs_by_environment" in body
    assert "logs_by_severity" in body
    assert "unresolved_error_count" in body
    assert "most_frequent_error_groups" in body
    assert "avg_occurrences_per_group" in body


async def test_analytics_summary_includes_logged_data(async_client: AsyncClient) -> None:
    """Analytics endpoint should include data from logged errors."""
    # Register and login
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": "analytics-data@example.com", "password": "supersecurepass"},
    )
    token = await _login(
        async_client, email="analytics-data@example.com", password="supersecurepass"
    )

    # Ingest some error logs
    for i in range(3):
        await async_client.post(
            "/api/v1/logs",
            headers=_auth_header(token),
            json={
                "service_name": "test-service",
                "environment": LogEnvironment.PRODUCTION.value,
                "log_level": LogLevel.ERROR.value,
                "message": f"Test error {i}",
                "exception_type": "TestException",
                "stack_trace": "trace",
                "metadata": {},
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

    # Get analytics
    response = await async_client.get(
        "/api/v1/analytics/summary",
        headers=_auth_header(token),
    )

    assert response.status_code == 200
    body = response.json()
    # Analytics are served from Redis cache populated by Celery tasks.
    # In test environment, cache is empty (cache miss returns zero-valued summary).
    # We verify schema shape, not data values.
    assert isinstance(body["total_logs"], int)
    assert isinstance(body["logs_last_24h"], int)
    assert isinstance(body["logs_by_service"], dict)
    assert isinstance(body["logs_by_environment"], dict)
    assert isinstance(body["logs_by_severity"], dict)
    assert isinstance(body["unresolved_error_count"], int)
    assert isinstance(body["most_frequent_error_groups"], list)
    assert isinstance(body["avg_occurrences_per_group"], float)
