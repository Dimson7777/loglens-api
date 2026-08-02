from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, cast

import pytest
from redis.exceptions import RedisError

from app.core.rate_limit import RedisLoginRateLimiter


class InMemoryRedisClient:
    def __init__(self) -> None:
        self._data: dict[str, int] = {}

    async def get(self, key: str) -> str | None:
        value = self._data.get(key)
        if value is None:
            return None
        return str(value)

    async def incr(self, key: str) -> int:
        value = self._data.get(key, 0) + 1
        self._data[key] = value
        return value

    async def expire(self, key: str, _: int) -> bool:
        return key in self._data

    async def delete(self, *keys: str) -> int:
        deleted = 0
        for key in keys:
            if key in self._data:
                del self._data[key]
                deleted += 1
        return deleted

    async def scan_iter(self, *, match: str) -> AsyncIterator[str]:
        prefix = match[:-1] if match.endswith("*") else match
        for key in list(self._data.keys()):
            if key.startswith(prefix):
                yield key


class FailingRedisClient:
    async def get(self, _: str) -> None:
        raise RedisError("redis unavailable")

    async def incr(self, _: str) -> int:
        raise RedisError("redis unavailable")

    async def expire(self, _: str, __: int) -> bool:
        raise RedisError("redis unavailable")

    async def delete(self, *_: str) -> int:
        raise RedisError("redis unavailable")

    async def scan_iter(self, *, match: str) -> AsyncIterator[str]:
        del match
        raise RedisError("redis unavailable")
        yield ""


@pytest.mark.asyncio
async def test_redis_rate_limiter_blocks_after_max_attempts() -> None:
    limiter = RedisLoginRateLimiter(
        client=cast(Any, InMemoryRedisClient()),
        max_attempts=3,
        window_seconds=60,
    )
    key = "127.0.0.1:test@example.com"

    assert await limiter.is_allowed(key)
    await limiter.add_failure(key)
    assert await limiter.is_allowed(key)
    await limiter.add_failure(key)
    assert await limiter.is_allowed(key)
    await limiter.add_failure(key)
    assert not await limiter.is_allowed(key)


@pytest.mark.asyncio
async def test_redis_rate_limiter_redis_unavailable_fails_open() -> None:
    limiter = RedisLoginRateLimiter(
        client=cast(Any, FailingRedisClient()),
        max_attempts=3,
        window_seconds=60,
    )
    key = "127.0.0.1:test@example.com"

    assert await limiter.is_allowed(key)
    await limiter.add_failure(key)
    await limiter.clear(key)
    await limiter.reset_all()
