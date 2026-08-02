from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.enums import LogEnvironment, LogLevel


class Log(Base):
    __tablename__ = "logs"
    __table_args__ = (
        Index("ix_logs_service_name", "service_name"),
        Index("ix_logs_environment", "environment"),
        Index("ix_logs_log_level", "log_level"),
        Index("ix_logs_fingerprint", "fingerprint"),
        Index("ix_logs_timestamp", "timestamp"),
        Index("ix_logs_error_group_id", "error_group_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    service_name: Mapped[str] = mapped_column(String(128), nullable=False)
    environment: Mapped[LogEnvironment] = mapped_column(
        Enum(
            LogEnvironment,
            name="log_environment",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    log_level: Mapped[LogLevel] = mapped_column(
        Enum(
            LogLevel,
            name="log_level",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_message: Mapped[str] = mapped_column(Text, nullable=False)
    exception_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stack_trace: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
    )
    fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_group_id: Mapped[int | None] = mapped_column(
        ForeignKey("error_groups.id", ondelete="SET NULL"),
        nullable=True,
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
