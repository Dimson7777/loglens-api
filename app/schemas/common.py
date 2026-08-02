from typing import Any

from pydantic import BaseModel


class PaginationMeta(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int


class ErrorData(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | list[Any] | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorData
    trace_id: str | None = None
