from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AnalysisPriority, ErrorAnalysisStatus


class AIAnalysisResult(BaseModel):
    summary: str = Field(min_length=1, max_length=4000)
    likely_root_cause: str = Field(min_length=1, max_length=4000)
    suggested_fix: str = Field(min_length=1, max_length=4000)
    confidence: float = Field(ge=0.0, le=1.0)
    affected_component: str = Field(min_length=1, max_length=255)
    recommended_priority: AnalysisPriority
    reasoning_summary: str = Field(min_length=1, max_length=4000)
    generated_at: datetime
    provider: str = Field(min_length=1, max_length=64)
    model: str = Field(min_length=1, max_length=128)
    latency_ms: int = Field(ge=0)


class ErrorAnalysisResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    error_group_id: int
    status: ErrorAnalysisStatus
    summary: str | None
    likely_root_cause: str | None
    suggested_fix: str | None
    confidence: float | None
    affected_component: str | None
    recommended_priority: AnalysisPriority | None
    reasoning_summary: str | None
    provider: str | None
    model: str | None
    latency_ms: int | None
    created_by: int | None
    created_at: datetime
    updated_at: datetime
