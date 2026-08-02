import asyncio
import os
import sys
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-with-at-least-32-characters")
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "true")
os.environ.setdefault("AI_PROVIDER", "mock")
os.environ.setdefault(
    "TEST_DATABASE_URL", "postgresql+asyncpg://loglens:loglens@localhost:5432/loglens"
)
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://loglens:loglens@localhost:5432/loglens")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

import app.models as models  # noqa: F401
from app.api.dependencies.system import ReadyCheck, get_db_ready_checker, get_redis_ready_checker
from app.core.config import get_settings
from app.core.rate_limit import get_login_rate_limiter, reset_login_rate_limiter
from app.core.redis import get_redis_client, reset_redis_client
from app.core.security import hash_password
from app.database.base import Base
from app.database.session import get_db_session
from app.main import create_app
from app.models.user import User, UserRole
from app.repositories.user import UserRepository


@pytest.fixture
def test_database_url(tmp_path: Path) -> str:
    del tmp_path
    return os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://loglens:loglens@db:5432/loglens",
    )


@pytest.fixture
async def test_engine(
    test_database_url: str,
) -> AsyncIterator[AsyncEngine]:
    get_settings.cache_clear()

    engine = create_async_engine(test_database_url, future=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    try:
        yield engine
    finally:
        await engine.dispose()
        get_settings.cache_clear()


@pytest.fixture
def session_factory(test_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
async def app(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[FastAPI]:
    reset_redis_client()
    reset_login_rate_limiter()
    await get_redis_client().flushdb()

    app_instance = create_app()

    async def override_get_db_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    async def _ready_checker() -> bool:
        return True

    async def override_db_ready_checker() -> ReadyCheck:
        return _ready_checker

    async def override_redis_ready_checker() -> ReadyCheck:
        return _ready_checker

    app_instance.dependency_overrides[get_db_session] = override_get_db_session
    app_instance.dependency_overrides[get_db_ready_checker] = override_db_ready_checker
    app_instance.dependency_overrides[get_redis_ready_checker] = override_redis_ready_checker

    rate_limiter = get_login_rate_limiter()
    await rate_limiter.reset_all()

    try:
        yield app_instance
    finally:
        app_instance.dependency_overrides.clear()
        reset_login_rate_limiter()
        await get_redis_client().flushdb()
        reset_redis_client()


@pytest.fixture
def user_factory(
    session_factory: async_sessionmaker[AsyncSession],
) -> Callable[..., Awaitable[User]]:
    async def _create_user(
        *,
        email: str,
        password: str,
        role: UserRole = UserRole.DEVELOPER,
        is_active: bool = True,
    ) -> User:
        async with session_factory() as session:
            user_repo = UserRepository(session)
            async with session.begin():
                user = await user_repo.create_user(
                    email=email.lower(),
                    password_hash=hash_password(password),
                    role=role,
                    is_active=is_active,
                )
            return user

    return _create_user


@pytest.fixture
async def async_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
