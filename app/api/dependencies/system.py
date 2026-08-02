from collections.abc import Awaitable, Callable

from app.core.redis import check_redis_connection
from app.database.session import check_database_connection

ReadyCheck = Callable[[], Awaitable[bool]]


async def get_db_ready_checker() -> ReadyCheck:
    return check_database_connection


async def get_redis_ready_checker() -> ReadyCheck:
    return check_redis_connection
