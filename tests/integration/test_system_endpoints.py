from collections.abc import Awaitable, Callable

from fastapi import FastAPI
from httpx import AsyncClient

from app.api.dependencies.system import ReadyCheck, get_db_ready_checker, get_redis_ready_checker


async def _check_true() -> bool:
    return True


async def _check_false() -> bool:
    return False


async def _db_checker_true() -> ReadyCheck:
    return _check_true


async def _redis_checker_true() -> ReadyCheck:
    return _check_true


async def _redis_checker_false() -> ReadyCheck:
    return _check_false


def _override_dependencies(
    app: FastAPI,
    *,
    db_dependency: Callable[[], Awaitable[ReadyCheck]],
    redis_dependency: Callable[[], Awaitable[ReadyCheck]],
) -> None:
    app.dependency_overrides[get_db_ready_checker] = db_dependency
    app.dependency_overrides[get_redis_ready_checker] = redis_dependency


async def test_health_endpoint(async_client: AsyncClient) -> None:
    response = await async_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_ready_endpoint_success(async_client: AsyncClient, app: FastAPI) -> None:
    _override_dependencies(
        app,
        db_dependency=_db_checker_true,
        redis_dependency=_redis_checker_true,
    )

    response = await async_client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "checks": {
            "database": "up",
            "redis": "up",
        },
    }


async def test_ready_endpoint_failure(async_client: AsyncClient, app: FastAPI) -> None:
    _override_dependencies(
        app,
        db_dependency=_db_checker_true,
        redis_dependency=_redis_checker_false,
    )

    response = await async_client.get("/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "service_unavailable"
    assert body["error"]["details"] == {
        "checks": {
            "database": "up",
            "redis": "down",
        }
    }


def test_dependency_type_contract() -> None:
    contract: ReadyCheck = _check_true
    assert callable(contract)
