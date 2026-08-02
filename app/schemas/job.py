from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import BackgroundJobStatus


class JobAcceptedResponse(BaseModel):
    job_id: str
    status: BackgroundJobStatus


class JobStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_id: str
    status: BackgroundJobStatus
    total_items: int
    processed_items: int
    success_count: int
    failure_count: int
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    error_summary: str | None
