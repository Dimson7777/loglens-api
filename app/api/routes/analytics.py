from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies.auth import require_developer_or_admin
from app.models.user import User
from app.schemas.analytics import AnalyticsSummaryResponse
from app.services.analytics import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["analytics"])


def get_analytics_service() -> AnalyticsService:
    """Dependency to get analytics service."""
    return AnalyticsService()


@router.get(
    "/summary",
    response_model=AnalyticsSummaryResponse,
)
async def get_analytics_summary(
    _: Annotated[User, Depends(require_developer_or_admin)],
    service: Annotated[AnalyticsService, Depends(get_analytics_service)],
) -> AnalyticsSummaryResponse:
    """
    Get analytics summary with cached aggregate metrics.

    Requires developer or admin role.

    The summary is computed and cached by background tasks.
    If cache is unavailable, an empty summary is returned.
    """
    return await service.get_summary()
