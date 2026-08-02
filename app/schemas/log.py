from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import LogEnvironment, LogLevel
from app.schemas.common import PaginationMeta

LogSortBy = Literal["timestamp", "created_at", "log_level"]
SortOrder = Literal["asc", "desc"]


class LogIngestRequest(BaseModel):
    service_name: str = Field(min_length=1, max_length=128)
    environment: LogEnvironment
    log_level: LogLevel
    message: str = Field(min_length=1, max_length=10_000)
    exception_type: str | None = Field(default=None, max_length=255)
    stack_trace: str | None = Field(default=None, max_length=100_000)
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime


class BulkLogItemRequest(LogIngestRequest):
    pass


class BulkLogIngestRequest(BaseModel):
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=128)
    logs: list[BulkLogItemRequest] = Field(min_length=1)


class LogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    service_name: str
    environment: LogEnvironment
    log_level: LogLevel
    message: str
    normalized_message: str
    exception_type: str | None
    stack_trace: str | None
    metadata: dict[str, Any] = Field(alias="metadata_")
    fingerprint: str | None
    error_group_id: int | None
    timestamp: datetime
    created_at: datetime


class BulkLogItemFailure(BaseModel):
    index: int
    error: str


class BulkLogIngestResponse(BaseModel):
    accepted_count: int
    failed_count: int
    logs: list[LogResponse]
    failures: list[BulkLogItemFailure] = Field(default_factory=list)


class LogListQuery(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    service: str | None = None
    environment: LogEnvironment | None = None
    level: LogLevel | None = None
    fingerprint: str | None = None
    error_group_id: int | None = None
    text: str | None = None
    from_timestamp: datetime | None = Field(default=None, alias="from")
    to_timestamp: datetime | None = Field(default=None, alias="to")
    sort_by: LogSortBy = "timestamp"
    sort_order: SortOrder = "desc"
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class LogListResponse(BaseModel):
    items: Sequence[LogResponse]
    pagination: PaginationMeta
