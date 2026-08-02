from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.enums import AnalysisPriority, ErrorAnalysisStatus


class ErrorAnalysis(Base):
    __tablename__ = "error_analyses"
    __table_args__ = (
        Index("ix_error_analyses_error_group_id", "error_group_id"),
        Index("ix_error_analyses_status", "status"),
        Index("ix_error_analyses_created_at", "created_at"),
        Index("ix_error_analyses_completed_at", "completed_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    error_group_id: Mapped[int] = mapped_column(
        ForeignKey("error_groups.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[ErrorAnalysisStatus] = mapped_column(
        Enum(
            ErrorAnalysisStatus,
            name="error_analysis_status",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=ErrorAnalysisStatus.PENDING,
        server_default=ErrorAnalysisStatus.PENDING.value,
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    likely_root_cause: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_fix: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    affected_component: Mapped[str | None] = mapped_column(String(255), nullable=True)
    recommended_priority: Mapped[AnalysisPriority | None] = mapped_column(
        Enum(
            AnalysisPriority,
            name="analysis_priority",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=True,
    )
    reasoning_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    raw_response_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
