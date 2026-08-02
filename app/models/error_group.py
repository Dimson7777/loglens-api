from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.models.enums import ErrorGroupSeverity, ErrorGroupStatus, LogEnvironment


class ErrorGroup(Base):
    __tablename__ = "error_groups"
    __table_args__ = (
        CheckConstraint(
            "occurrence_count >= 0",
            name="ck_error_groups_occurrence_count_non_negative",
        ),
        Index(
            "ix_error_groups_service_environment_fingerprint",
            "service_name",
            "environment",
            "fingerprint",
            unique=True,
        ),
        Index("ix_error_groups_status", "status"),
        Index("ix_error_groups_severity", "severity"),
        Index("ix_error_groups_assigned_to", "assigned_to"),
        Index("ix_error_groups_last_seen", "last_seen"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    service_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    environment: Mapped[LogEnvironment] = mapped_column(
        Enum(
            LogEnvironment,
            name="log_environment",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
    )
    exception_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    occurrence_count: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=1,
        server_default="1",
    )
    status: Mapped[ErrorGroupStatus] = mapped_column(
        Enum(
            ErrorGroupStatus,
            name="error_group_status",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=ErrorGroupStatus.UNRESOLVED,
        server_default=ErrorGroupStatus.UNRESOLVED.value,
    )
    severity: Mapped[ErrorGroupSeverity] = mapped_column(
        Enum(
            ErrorGroupSeverity,
            name="error_group_severity",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        nullable=False,
        default=ErrorGroupSeverity.MEDIUM,
        server_default=ErrorGroupSeverity.MEDIUM.value,
    )
    assigned_to: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
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
