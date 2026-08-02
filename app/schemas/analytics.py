from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ErrorGroupSummary(BaseModel):
    group_id: int
    title: str
    occurrence_count: int


class AnalyticsSummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    generated_at: datetime
    total_logs: int = Field(description="Total logs in database")
    logs_last_24h: int = Field(description="Logs ingested in last 24 hours")
    logs_by_service: dict[str, int] = Field(description="Log count by service name (last 24h)")
    logs_by_environment: dict[str, int] = Field(description="Log count by environment (last 24h)")
    logs_by_severity: dict[str, int] = Field(description="Log count by severity level (last 24h)")
    unresolved_error_count: int = Field(description="Total unresolved error groups")
    most_frequent_error_groups: list[ErrorGroupSummary] = Field(
        description="Top 10 most frequent error groups"
    )
    avg_occurrences_per_group: float = Field(description="Average occurrences per error group")
