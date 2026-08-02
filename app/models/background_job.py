from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.enums import BackgroundJobStatus, BackgroundJobType


class BackgroundJob(Base):
    __tablename__ = "background_jobs"
    __table_args__ = (
        CheckConstraint("total_items >= 0", name="ck_background_jobs_total_items_non_negative"),
        CheckConstraint(
            "processed_items >= 0",
            name="ck_background_jobs_processed_items_non_negative",
        ),
        CheckConstraint(
            "success_count >= 0",
            name="ck_background_jobs_success_count_non_negative",
        ),
        CheckConstraint(
            "failure_count >= 0",
            name="ck_background_jobs_failure_count_non_negative",
        ),
        Index("ix_background_jobs_status", "status"),
        Index("ix_background_jobs_created_at", "created_at"),
        Index("ix_background_jobs_completed_at", "completed_at"),
        Index("ix_background_jobs_scope_key", "scope_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_type: Mapped[BackgroundJobType] = mapped_column(
        Enum(
            BackgroundJobType,
            name="background_job_type",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    status: Mapped[BackgroundJobStatus] = mapped_column(
        Enum(
            BackgroundJobStatus,
            name="background_job_status",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=BackgroundJobStatus.PENDING,
        server_default=BackgroundJobStatus.PENDING.value,
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    total_items: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    processed_items: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    success_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    failure_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    scope_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
