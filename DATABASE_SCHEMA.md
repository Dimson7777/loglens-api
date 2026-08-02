# LogLens API Database Schema

## 1. Database Engine

- PostgreSQL 16+
- SQLAlchemy 2.0 async ORM
- Alembic migrations for schema evolution
- UTC timezone-aware timestamps only

## 2. Entity Overview

Primary tables:
- users
- logs
- error_groups
- ai_analyses
- ingestion_jobs

## 3. Enumerations

role_enum:
- admin
- developer

environment_enum:
- development
- staging
- production

log_level_enum:
- debug
- info
- warning
- error
- critical

error_group_status_enum:
- unresolved
- investigating
- resolved
- ignored

severity_enum:
- low
- medium
- high
- critical

## 4. Tables and Columns

### users

Columns:
- id: UUID, PK
- email: varchar(320), unique, not null
- password_hash: varchar, not null
- role: role_enum, not null, default developer
- is_active: boolean, not null, default true
- created_at: timestamptz, not null
- updated_at: timestamptz, not null

Indexes:
- unique index on email
- index on role

### error_groups

Columns:
- id: UUID, PK
- fingerprint: varchar(128), not null
- title: varchar(512), not null
- service_name: varchar(128), not null
- environment: environment_enum, not null
- first_seen: timestamptz, not null
- last_seen: timestamptz, not null
- occurrence_count: bigint, not null, default 1
- status: error_group_status_enum, not null, default unresolved
- severity: severity_enum, not null, default medium
- assigned_to: UUID, nullable, FK users.id
- created_at: timestamptz, not null
- updated_at: timestamptz, not null

Constraints:
- unique(service_name, environment, fingerprint)
- occurrence_count >= 0

Indexes:
- unique index on (service_name, environment, fingerprint)
- index on status
- index on severity
- index on last_seen desc
- index on service_name
- index on environment

### logs

Columns:
- id: UUID, PK
- service_name: varchar(128), not null
- environment: environment_enum, not null
- log_level: log_level_enum, not null
- message: text, not null
- stack_trace: text, nullable
- timestamp: timestamptz, not null
- metadata: jsonb, not null, default {}
- fingerprint: varchar(128), not null
- exception_type: varchar(256), nullable
- error_group_id: UUID, nullable, FK error_groups.id
- ingested_by_user_id: UUID, nullable, FK users.id
- created_at: timestamptz, not null

Constraints:
- message length > 0

Indexes:
- index on service_name
- index on environment
- index on log_level
- index on fingerprint
- index on timestamp desc
- index on error_group_id
- gin index on metadata jsonb
- full-text index for message and stack_trace (tsvector)

### ai_analyses

Columns:
- id: UUID, PK
- error_group_id: UUID, not null, FK error_groups.id
- provider: varchar(64), not null
- model: varchar(128), nullable
- summary: text, not null
- likely_root_cause: text, not null
- suggested_fix: text, not null
- confidence: numeric(4,3), not null
- affected_component: varchar(256), not null
- recommended_priority: varchar(64), not null
- raw_response: jsonb, not null
- created_at: timestamptz, not null

Constraints:
- confidence between 0 and 1

Indexes:
- index on error_group_id
- index on created_at desc

### ingestion_jobs

Columns:
- id: UUID, PK
- idempotency_key: varchar(128), unique, not null
- requested_by_user_id: UUID, nullable, FK users.id
- total_records: integer, not null
- processed_records: integer, not null, default 0
- status: varchar(32), not null
- error_message: text, nullable
- created_at: timestamptz, not null
- updated_at: timestamptz, not null

Constraints:
- total_records >= 0
- processed_records >= 0

Indexes:
- unique index on idempotency_key
- index on status
- index on created_at desc

## 5. Referential Behavior

- logs.error_group_id references error_groups.id with on delete set null.
- logs.ingested_by_user_id references users.id with on delete set null.
- error_groups.assigned_to references users.id with on delete set null.
- ai_analyses.error_group_id references error_groups.id with on delete cascade.

## 6. Query Patterns and Optimization Notes

Expected high-frequency queries:
- recent logs by service/env/level/date range
- unresolved groups by service/env
- top recurring groups by occurrence_count
- full-text search on message/stack traces

Optimization approach:
- composite indexes for common filter combinations in later migrations if needed.
- partial index on logs where log_level in (error, critical) for analytics-heavy workloads.
- keep heavy aggregations in analytics endpoint optimized by date and indexed dimensions.

## 7. Transactional Rules

On ingest:
- insert log row
- upsert matching error group
- increment occurrence_count and update last_seen
- bind log.error_group_id
All above inside one transaction per record or per chunk.

## 8. Migration Strategy

Migration 0001:
- create enums
- create all tables
- create indexes and constraints

Migration 0002+:
- additive schema changes only where possible
- explicit data backfills for new non-null fields
- rollback-safe transformation steps

## 9. Phase 4 Addendum

Current async job and analysis persistence is implemented with these tables:

### background_jobs

Key columns:
- id: UUID, PK
- job_type: enum
- status: enum (`pending|running|completed|partially_completed|failed`)
- created_by: int nullable
- payload: JSONB
- total_items: int
- processed_items: int
- success_count: int
- failure_count: int
- celery_task_id: varchar nullable
- idempotency_key: varchar nullable
- scope_key: varchar nullable
- error_summary: text nullable
- started_at: timestamptz nullable
- completed_at: timestamptz nullable
- created_at, updated_at: timestamptz

Important indexes and constraints:
- unique idempotency index (when idempotency key is present)
- unique active-scope index for `scope_key` while status is `pending` or `running`
- progress counters constrained to non-negative values

### error_analyses

Key columns:
- id: bigint, PK
- error_group_id: int, FK error_groups.id
- status: enum (`pending|completed|failed`)
- created_by: int nullable
- summary, likely_root_cause, suggested_fix: text nullable while pending
- confidence: numeric with range constraint
- provider, model: varchar nullable
- latency_ms: int nullable
- raw_response_metadata: JSONB
- completed_at: timestamptz nullable
- created_at, updated_at: timestamptz

Important indexes and constraints:
- index on `(error_group_id, created_at desc)` for latest/history queries
- confidence constrained to `[0, 1]` when populated
