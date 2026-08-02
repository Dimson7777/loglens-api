from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ErrorGroupSeverity, ErrorGroupStatus, LogEnvironment
from app.schemas.common import PaginationMeta

ErrorGroupSortBy = Literal["last_seen", "occurrence_count", "created_at"]
SortOrder = Literal["asc", "desc"]


class ErrorGroupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fingerprint: str
    title: str
    service_name: str
    environment: LogEnvironment
    exception_type: str | None
    first_seen: datetime
    last_seen: datetime
    occurrence_count: int
    status: ErrorGroupStatus
    severity: ErrorGroupSeverity
    assigned_to: int | None
    created_at: datetime
    updated_at: datetime


class ErrorGroupListQuery(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    service: str | None = None
    environment: LogEnvironment | None = None
    status: ErrorGroupStatus | None = None
    severity: ErrorGroupSeverity | None = None
    assigned_to: int | None = None
    text: str | None = None
    from_timestamp: datetime | None = Field(default=None, alias="from")
    to_timestamp: datetime | None = Field(default=None, alias="to")
    sort_by: ErrorGroupSortBy = "last_seen"
    sort_order: SortOrder = "desc"
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class ErrorGroupListResponse(BaseModel):
    items: Sequence[ErrorGroupResponse]
    pagination: PaginationMeta


class ErrorGroupStatusUpdateRequest(BaseModel):
    status: ErrorGroupStatus


class ErrorGroupAssignmentUpdateRequest(BaseModel):
    assigned_to: int | None = None
