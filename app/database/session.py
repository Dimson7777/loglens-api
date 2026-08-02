import asyncio
from collections.abc import AsyncIterator
from typing import cast

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.observability.metrics import (
    instrument_sqlalchemy_engine,
    observe_database_query,
    set_database_availability,
)
from app.observability.tracing import instrument_sqlalchemy

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            future=True,
            pool_pre_ping=True,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_timeout=settings.database_pool_timeout_seconds,
            pool_recycle=settings.database_pool_recycle_seconds,
        )
        instrument_sqlalchemy_engine(_engine.sync_engine)
        if settings.otel_enabled:
            instrument_sqlalchemy(_engine.sync_engine)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            autoflush=False,
            expire_on_commit=False,
        )
    return _session_factory


async def get_db_session() -> AsyncIterator[AsyncSession]:
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session


async def dispose_engine() -> None:
    global _engine
    global _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None


async def check_database_connection() -> bool:
    settings = get_settings()
    engine = get_engine()

    try:
        started_at = asyncio.get_running_loop().time()
        async with engine.connect() as connection:
            result = await asyncio.wait_for(
                connection.execute(text("SELECT 1")),
                timeout=settings.ready_check_timeout_seconds,
            )
            is_up = cast(int, result.scalar_one()) == 1
            observe_database_query("ready_check", asyncio.get_running_loop().time() - started_at)
            set_database_availability(is_up)
            return is_up
    except Exception:
        set_database_availability(False)
        return False
