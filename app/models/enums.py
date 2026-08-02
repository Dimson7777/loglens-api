from __future__ import annotations

from enum import StrEnum


class LogEnvironment(StrEnum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class LogLevel(StrEnum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ErrorGroupStatus(StrEnum):
    UNRESOLVED = "unresolved"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    IGNORED = "ignored"


class ErrorGroupSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class BackgroundJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIALLY_COMPLETED = "partially_completed"


class BackgroundJobType(StrEnum):
    BULK_LOG_INGEST = "bulk_log_ingest"
    ERROR_GROUP_ANALYSIS = "error_group_analysis"
    LOG_CLEANUP = "log_cleanup"
    ANALYTICS_RECALCULATION = "analytics_recalculation"


class ErrorAnalysisStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalysisPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
