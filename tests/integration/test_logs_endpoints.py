from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

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


async def test_single_log_ingestion_creates_group(async_client: AsyncClient) -> None:
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": "devlogs@example.com", "password": "supersecurepass"},
    )
    token = await _login(async_client, email="devlogs@example.com", password="supersecurepass")

    response = await async_client.post(
        "/api/v1/logs",
        headers=_auth_header(token),
        json={
            "service_name": "payments-api",
            "environment": "production",
            "log_level": "error",
            "message": (
                "Failed to save order 12345 for request 9f3b6e4b-4e9d-4d26-9f1d-6bce6d1d2d11"
            ),
            "exception_type": "IntegrityError",
            "stack_trace": 'File "/app/app/services/orders.py", line 44, in save_order',
            "metadata": {"order_id": 12345},
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["service_name"] == "payments-api"
    assert body["fingerprint"] is not None
    assert body["error_group_id"] is not None


async def test_duplicate_logs_share_error_group(async_client: AsyncClient) -> None:
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": "duplogs@example.com", "password": "supersecurepass"},
    )
    token = await _login(async_client, email="duplogs@example.com", password="supersecurepass")
    payload = {
        "service_name": "billing-api",
        "environment": "production",
        "log_level": "error",
        "message": "Failed to save order 12345",
        "exception_type": "IntegrityError",
        "stack_trace": 'File "/app/app/services/orders.py", line 44, in save_order',
        "metadata": {},
        "timestamp": datetime.now(UTC).isoformat(),
    }

    first_response = await async_client.post(
        "/api/v1/logs",
        headers=_auth_header(token),
        json=payload,
    )
    second_response = await async_client.post(
        "/api/v1/logs",
        headers=_auth_header(token),
        json=payload,
    )

    first_body = cast(dict[str, Any], first_response.json())
    second_body = cast(dict[str, Any], second_response.json())
    assert first_body["error_group_id"] == second_body["error_group_id"]

    group_response = await async_client.get(
        f"/api/v1/error-groups/{first_body['error_group_id']}",
        headers=_auth_header(token),
    )
    group_body = group_response.json()
    assert group_body["occurrence_count"] == 2


async def test_bulk_ingestion_is_idempotent_with_key(async_client: AsyncClient) -> None:
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": "bulkdev@example.com", "password": "supersecurepass"},
    )
    token = await _login(async_client, email="bulkdev@example.com", password="supersecurepass")
    payload = {
        "idempotency_key": f"bulk-batch-{uuid4()}",
        "logs": [
            {
                "service_name": "checkout-api",
                "environment": "staging",
                "log_level": "warning",
                "message": "Slow payment response for request 1",
                "exception_type": None,
                "stack_trace": None,
                "metadata": {"request_id": "abc"},
                "timestamp": datetime.now(UTC).isoformat(),
            },
            {
                "service_name": "checkout-api",
                "environment": "staging",
                "log_level": "info",
                "message": "Payment completed",
                "exception_type": None,
                "stack_trace": None,
                "metadata": {"request_id": "def"},
                "timestamp": datetime.now(UTC).isoformat(),
            },
        ],
    }

    first_response = await async_client.post(
        "/api/v1/logs/bulk",
        headers=_auth_header(token),
        json=payload,
    )
    second_response = await async_client.post(
        "/api/v1/logs/bulk",
        headers=_auth_header(token),
        json=payload,
    )

    assert first_response.status_code == 202
    assert second_response.status_code == 202

    first_job_id = first_response.json()["job_id"]
    second_job_id = second_response.json()["job_id"]
    assert first_job_id == second_job_id

    job_response = await async_client.get(
        f"/api/v1/jobs/{first_job_id}", headers=_auth_header(token)
    )
    assert job_response.status_code == 200
    job_payload = job_response.json()
    assert job_payload["total_items"] == 2
    assert job_payload["processed_items"] == 2
    assert job_payload["success_count"] == 2
    assert job_payload["failure_count"] == 0
    assert job_payload["status"] == "completed"


async def test_log_filtering_pagination_and_deletion(
    async_client: AsyncClient,
    user_factory: Callable[..., Awaitable[User]],
) -> None:
    await user_factory(
        email="adminlogs@example.com",
        password="supersecurepass",
        role=UserRole.ADMIN,
    )
    token = await _login(async_client, email="adminlogs@example.com", password="supersecurepass")

    for index in range(3):
        await async_client.post(
            "/api/v1/logs",
            headers=_auth_header(token),
            json={
                "service_name": "search-api",
                "environment": "production",
                "log_level": "info",
                "message": f"Search request {index}",
                "exception_type": None,
                "stack_trace": None,
                "metadata": {"index": index},
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

    list_response = await async_client.get(
        "/api/v1/logs?page=1&page_size=2&service=search-api&sort_by=timestamp&sort_order=desc",
        headers=_auth_header(token),
    )
    body = list_response.json()
    assert body["pagination"]["total_items"] == 3
    assert body["pagination"]["page_size"] == 2
    assert len(body["items"]) == 2

    log_id = body["items"][0]["id"]
    delete_response = await async_client.delete(
        f"/api/v1/logs/{log_id}",
        headers=_auth_header(token),
    )
    assert delete_response.status_code == 204

    get_response = await async_client.get(f"/api/v1/logs/{log_id}", headers=_auth_header(token))
    assert get_response.status_code == 404


async def test_bulk_ingestion_idempotency_key_conflict(async_client: AsyncClient) -> None:
    await async_client.post(
        "/api/v1/auth/register",
        json={"email": "bulkconflict@example.com", "password": "supersecurepass"},
    )
    token = await _login(async_client, email="bulkconflict@example.com", password="supersecurepass")
    key = f"bulk-key-{uuid4()}"

    first_payload = {
        "idempotency_key": key,
        "logs": [
            {
                "service_name": "ingest-api",
                "environment": "staging",
                "log_level": "info",
                "message": "first payload",
                "exception_type": None,
                "stack_trace": None,
                "metadata": {},
                "timestamp": datetime.now(UTC).isoformat(),
            }
        ],
    }
    second_payload = {
        "idempotency_key": key,
        "logs": [
            {
                "service_name": "ingest-api",
                "environment": "staging",
                "log_level": "info",
                "message": "second payload",
                "exception_type": None,
                "stack_trace": None,
                "metadata": {},
                "timestamp": datetime.now(UTC).isoformat(),
            }
        ],
    }

    first_response = await async_client.post(
        "/api/v1/logs/bulk",
        headers=_auth_header(token),
        json=first_payload,
    )
    second_response = await async_client.post(
        "/api/v1/logs/bulk",
        headers=_auth_header(token),
        json=second_payload,
    )

    assert first_response.status_code == 202
    assert second_response.status_code == 409
