import asyncio

import redis.asyncio as redis

from app.core.config import get_settings
from app.observability.metrics import MetricsRedis, observe_redis_command, set_redis_availability

_redis_client: redis.Redis | None = None  # type: ignore[type-arg]


def get_redis_client() -> redis.Redis:  # type: ignore[type-arg]
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = MetricsRedis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_timeout=settings.redis_socket_timeout_seconds,
            health_check_interval=settings.redis_health_check_interval_seconds,
        )
    return _redis_client


async def close_redis_client() -> None:
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None


def reset_redis_client() -> None:
    global _redis_client
    _redis_client = None


async def check_redis_connection() -> bool:
    settings = get_settings()
    client = get_redis_client()
    started_at = asyncio.get_running_loop().time()
    try:
        result = await asyncio.wait_for(client.ping(), timeout=settings.ready_check_timeout_seconds)
        observe_redis_command("ping", asyncio.get_running_loop().time() - started_at)
        set_redis_availability(bool(result))
        return bool(result)
    except (TimeoutError, redis.RedisError):
        set_redis_availability(False)
        return False
