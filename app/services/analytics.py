from __future__ import annotations

import json
from datetime import UTC, datetime

import structlog
from redis.exceptions import RedisError

from app.core.config import get_settings
from app.core.redis import get_redis_client
from app.schemas.analytics import AnalyticsSummaryResponse

logger = structlog.get_logger(__name__)

_ANALYTICS_CACHE_KEY = "analytics:summary:v1"


class AnalyticsService:
    """Service for retrieving analytics and summary data."""

    def __init__(self) -> None:
        self._redis = get_redis_client()
        self._settings = get_settings()

    async def get_summary(self) -> AnalyticsSummaryResponse:
        """
        Retrieve cached analytics summary, or return empty if unavailable.

        The summary is computed and cached by the recalculate_summary_analytics_task
        which runs on a schedule (default: every 5 minutes).
        """
        try:
            cached = await self._redis.get(_ANALYTICS_CACHE_KEY)
            if not cached:
                logger.warning("Analytics cache miss")
                return self._empty_summary()

            payload = json.loads(cached)
            return AnalyticsSummaryResponse.model_validate(payload)
        except (RedisError, ValueError) as e:
            logger.exception("Failed to retrieve analytics cache", error=str(e))
            return self._empty_summary()

    def _empty_summary(self) -> AnalyticsSummaryResponse:
        """Return an empty analytics summary."""
        return AnalyticsSummaryResponse(
            generated_at=datetime.now(UTC),
            total_logs=0,
            logs_last_24h=0,
            logs_by_service={},
            logs_by_environment={},
            logs_by_severity={},
            unresolved_error_count=0,
            most_frequent_error_groups=[],
            avg_occurrences_per_group=0.0,
        )
