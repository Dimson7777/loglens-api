from __future__ import annotations

import json
from contextlib import suppress
from datetime import UTC, datetime
from hashlib import sha256
from math import ceil

from redis.exceptions import RedisError
from sqlalchemy import Select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.core.redis import get_redis_client
from app.models.enums import BackgroundJobType, ErrorGroupSeverity, LogLevel
from app.models.error_group import ErrorGroup
from app.models.log import Log
from app.models.user import User
from app.observability.metrics import observe_log_ingestion
from app.repositories.error_group import ErrorGroupRepository
from app.repositories.log import LogRepository
from app.schemas.common import PaginationMeta
from app.schemas.job import JobAcceptedResponse
from app.schemas.log import (
    BulkLogIngestRequest,
    LogIngestRequest,
    LogListQuery,
    LogListResponse,
    LogResponse,
)
from app.services.fingerprint import (
    FingerprintInput,
    generate_fingerprint,
    normalize_message,
)
from app.services.jobs import JobService

_ERROR_LEVELS = {LogLevel.WARNING, LogLevel.ERROR, LogLevel.CRITICAL}


def _as_utc_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class LogService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._log_repo = LogRepository(session)
        self._error_group_repo = ErrorGroupRepository(session)
        self._redis = get_redis_client()
        self._settings = get_settings()

    def _severity_for_level(self, log_level: LogLevel) -> ErrorGroupSeverity:
        if log_level == LogLevel.WARNING:
            return ErrorGroupSeverity.MEDIUM
        if log_level == LogLevel.ERROR:
            return ErrorGroupSeverity.HIGH
        return ErrorGroupSeverity.CRITICAL

    def _should_group(self, log_level: LogLevel) -> bool:
        return log_level in _ERROR_LEVELS

    def _group_title(self, payload: LogIngestRequest, normalized_message: str) -> str:
        if payload.exception_type:
            return payload.exception_type[:512]
        return normalized_message[:512]

    async def _persist_log(self, payload: LogIngestRequest) -> Log:
        normalized_message = normalize_message(payload.message)
        timestamp = _as_utc_aware(payload.timestamp)
        fingerprint = None
        error_group: ErrorGroup | None = None

        if self._should_group(payload.log_level):
            fingerprint = generate_fingerprint(
                FingerprintInput(
                    service_name=payload.service_name,
                    normalized_message=normalized_message,
                    exception_type=payload.exception_type,
                    stack_trace=payload.stack_trace,
                )
            )
            error_group = await self._error_group_repo.upsert_group(
                fingerprint=fingerprint,
                title=self._group_title(payload, normalized_message),
                service_name=payload.service_name,
                environment=payload.environment,
                exception_type=payload.exception_type,
                first_seen=timestamp,
                last_seen=timestamp,
                severity=self._severity_for_level(payload.log_level),
            )

        log = await self._log_repo.create_log(
            service_name=payload.service_name,
            environment=payload.environment,
            log_level=payload.log_level,
            message=payload.message,
            normalized_message=normalized_message,
            exception_type=payload.exception_type,
            stack_trace=payload.stack_trace,
            metadata_=payload.metadata,
            fingerprint=fingerprint,
            error_group_id=error_group.id if error_group is not None else None,
            timestamp=timestamp,
        )
        return log

    async def ingest_log(self, payload: LogIngestRequest) -> Log:
        log = await self._persist_log(payload)
        await self._session.commit()
        observe_log_ingestion("single", 1)
        return log

    async def enqueue_bulk_ingestion_job(
        self,
        *,
        payload: BulkLogIngestRequest,
        current_user: User,
    ) -> JobAcceptedResponse:
        request_hash = sha256(
            json.dumps(
                [item.model_dump(mode="json") for item in payload.logs],
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        job_service = JobService(self._session)
        job = await job_service.create_job(
            job_type=BackgroundJobType.BULK_LOG_INGEST,
            payload={
                "request_hash": request_hash,
                "logs": [item.model_dump(mode="json") for item in payload.logs],
            },
            total_items=len(payload.logs),
            created_by=current_user.id,
            idempotency_key=payload.idempotency_key,
            scope_key=None,
        )

        if payload.idempotency_key is not None:
            with suppress(RedisError):
                await self._redis.set(
                    f"ingest:bulk:{payload.idempotency_key}",
                    json.dumps({"job_id": job.id, "request_hash": request_hash}),
                    ex=self._settings.bulk_idempotency_ttl_seconds,
                )

        return JobService.to_accepted_response(job)

    async def get_log(self, log_id: int) -> Log:
        log = await self._log_repo.get_by_id(log_id)
        if log is None:
            raise NotFoundError(resource_name="Log")
        return log

    async def delete_log(self, log_id: int) -> None:
        log = await self.get_log(log_id)
        await self._log_repo.delete_log(log=log)
        await self._session.commit()

    def _sort_statement(
        self,
        stmt: Select[tuple[Log]],
        sort_by: str,
        sort_order: str,
    ) -> Select[tuple[Log]]:
        column_map = {
            "timestamp": Log.timestamp,
            "created_at": Log.created_at,
            "log_level": Log.log_level,
        }
        column = column_map[sort_by]
        if sort_order == "asc":
            return stmt.order_by(column.asc(), Log.id.asc())
        return stmt.order_by(desc(column), Log.id.desc())

    async def list_logs(self, query: LogListQuery) -> LogListResponse:
        stmt = self._log_repo.build_query(
            service=query.service,
            environment=query.environment,
            level=query.level,
            fingerprint=query.fingerprint,
            error_group_id=query.error_group_id,
            text=query.text,
            from_timestamp=query.from_timestamp,
            to_timestamp=query.to_timestamp,
        )
        stmt = self._sort_statement(stmt, query.sort_by, query.sort_order)
        total_items = await self._log_repo.count_logs(stmt)
        offset = (query.page - 1) * query.page_size
        stmt = stmt.limit(query.page_size).offset(offset)
        logs = await self._log_repo.list_logs(stmt)
        total_pages = ceil(total_items / query.page_size) if total_items else 0
        return LogListResponse(
            items=[LogResponse.model_validate(log) for log in logs],
            pagination=PaginationMeta(
                page=query.page,
                page_size=query.page_size,
                total_items=total_items,
                total_pages=total_pages,
            ),
        )
