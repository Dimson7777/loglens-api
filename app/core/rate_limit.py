from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, cast

from redis.exceptions import RedisError

from app.core.config import get_settings
from app.core.redis import get_redis_client


class LoginRateLimiter(Protocol):
    async def is_allowed(self, key: str) -> bool: ...

    async def add_failure(self, key: str) -> None: ...

    async def clear(self, key: str) -> None: ...

    async def reset_all(self) -> None: ...


class RedisClientLike(Protocol):
    async def get(self, key: str) -> str | bytes | None: ...

    async def incr(self, key: str) -> int: ...

    async def expire(self, key: str, time: int) -> bool: ...

    async def delete(self, *keys: str) -> int: ...

    def scan_iter(self, *, match: str) -> AsyncIterator[str | bytes]: ...


class RedisLoginRateLimiter:
    def __init__(
        self,
        *,
        client: RedisClientLike,
        max_attempts: int,
        window_seconds: int,
        key_prefix: str = "auth:login_attempts",
    ) -> None:
        self._client = client
        self._max_attempts = max_attempts
        self._window_seconds = window_seconds
        self._key_prefix = key_prefix

    def _redis_key(self, key: str) -> str:
        return f"{self._key_prefix}:{key}"

    async def is_allowed(self, key: str) -> bool:
        try:
            count = await self._client.get(self._redis_key(key))
        except RedisError:
            return True

        if count is None:
            return True
        if isinstance(count, bytes):
            count = count.decode("utf-8")
        return int(count) < self._max_attempts

    async def add_failure(self, key: str) -> None:
        redis_key = self._redis_key(key)
        try:
            count = await self._client.incr(redis_key)
            if count == 1:
                await self._client.expire(redis_key, self._window_seconds)
        except RedisError:
            return

    async def clear(self, key: str) -> None:
        try:
            await self._client.delete(self._redis_key(key))
        except RedisError:
            return

    async def reset_all(self) -> None:
        pattern = f"{self._key_prefix}:*"
        try:
            keys: list[str] = []
            async for key in self._client.scan_iter(match=pattern):
                keys.append(key.decode("utf-8") if isinstance(key, bytes) else key)
            if keys:
                await self._client.delete(*keys)
        except RedisError:
            return


_rate_limiter: LoginRateLimiter | None = None


def get_login_rate_limiter() -> LoginRateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        settings = get_settings()
        _rate_limiter = RedisLoginRateLimiter(
            client=cast(RedisClientLike, get_redis_client()),
            max_attempts=settings.login_rate_limit_attempts,
            window_seconds=settings.login_rate_limit_window_seconds,
        )
    assert _rate_limiter is not None
    return _rate_limiter


def reset_login_rate_limiter() -> None:
    global _rate_limiter
    _rate_limiter = None
