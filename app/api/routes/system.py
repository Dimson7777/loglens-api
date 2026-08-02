from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies.system import ReadyCheck, get_db_ready_checker, get_redis_ready_checker
from app.core.exceptions import ServiceUnavailableError
from app.schemas.common import ErrorEnvelope
from app.schemas.system import HealthResponse, ReadyResponse

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get(
    "/ready",
    response_model=ReadyResponse,
    responses={503: {"model": ErrorEnvelope}},
)
async def ready(
    db_checker: Annotated[ReadyCheck, Depends(get_db_ready_checker)],
    redis_checker: Annotated[ReadyCheck, Depends(get_redis_ready_checker)],
) -> ReadyResponse:
    checks = {
        "database": "up" if await db_checker() else "down",
        "redis": "up" if await redis_checker() else "down",
    }

    if any(value == "down" for value in checks.values()):
        raise ServiceUnavailableError(
            "One or more dependencies are unavailable.",
            details={"checks": checks},
        )

    return ReadyResponse(status="ready", checks={"database": "up", "redis": "up"})
