# LogLens API Specification

## 1. Base

- Base path: /api/v1
- Content type: application/json
- Auth: Bearer JWT unless marked public
- API docs: /docs and /openapi.json

## 2. Common Response Envelope

Success responses return resource-specific payloads.
Error responses use consistent shape:
- error.code: machine-readable string
- error.message: safe message
- error.details: optional validation metadata
- trace_id: request correlation id

## 3. Authentication Endpoints

### POST /api/v1/auth/register (public)

Request:
- email: EmailStr
- password: string, minimum length 8

Response 201:
- id
- email
- role
- is_active
- created_at
- updated_at

Errors:
- 409 email_already_registered

### POST /api/v1/auth/login (public)

Request:
- email
- password

Response 200:
- token: {access_token, refresh_token, token_type, expires_in_seconds, refresh_expires_in_seconds}

Errors:
- 401 authentication_failed (invalid credentials)
- 403 inactive_user
- 429 rate_limit_exceeded

### POST /api/v1/auth/refresh (public)

Request:
- refresh_token

Response 200:
- token: {access_token, refresh_token, token_type, expires_in_seconds, refresh_expires_in_seconds}

Behavior:
- refresh tokens rotate on every successful refresh
- token family is revoked if token reuse is detected

Errors:
- 401 authentication_failed (invalid or revoked refresh token)

### POST /api/v1/auth/logout (public)

Request:
- refresh_token

Response 200:
- status: ok

Behavior:
- revokes the supplied refresh token

### POST /api/v1/auth/logout-all (authenticated)

Response 200:
- status: ok

Behavior:
- revokes all refresh tokens for the current user

### GET /api/v1/auth/me (authenticated)

Response 200:
- id
- email
- role
- is_active

## 4. User Management Endpoints

### GET /api/v1/users (admin)

Response 200:
- list of users:
	- id
	- email
	- role
	- is_active
	- created_at
	- updated_at

### PATCH /api/v1/users/{user_id}/role (admin)

Request:
- role: admin | developer

Response 200:
- full user payload

### PATCH /api/v1/users/{user_id}/status (admin)

Request:
- is_active: boolean

Response 200:
- full user payload

Errors:
- 403 forbidden
- 404 not_found

## 5. Log Endpoints

### POST /api/v1/logs (developer, admin)

Request:
- service_name
- environment
- log_level
- message
- stack_trace optional
- timestamp
- metadata optional object

Response 201:
- id
- fingerprint
- error_group_id optional
- created_at

### POST /api/v1/logs/bulk (developer, admin)

Request:
- idempotency_key
- logs: array with bounded max size

Response 202:
- job_id
- status
- accepted_count

### GET /api/v1/logs (developer, admin)

Query params:
- service
- environment
- level
- fingerprint
- status (via group join)
- text
- from
- to
- sort_by (timestamp, created_at, log_level)
- sort_order (asc, desc)
- page
- page_size

Response 200:
- items
- pagination: page, page_size, total_items, total_pages

### GET /api/v1/logs/{log_id} (developer, admin)

Response 200:
- full log record

### DELETE /api/v1/logs/{log_id} (admin)

Response 204: no body

## 6. Error Group Endpoints

### GET /api/v1/error-groups (developer, admin)

Query params:
- service
- environment
- status
- severity
- fingerprint
- text
- from
- to
- sort_by (last_seen, occurrence_count, created_at)
- sort_order (asc, desc)
- page
- page_size

Response 200:
- items
- pagination

### GET /api/v1/error-groups/{group_id} (developer, admin)

Response 200:
- full error group with latest analysis (if present)

### PATCH /api/v1/error-groups/{group_id}/status (admin)

Request:
- status

Response 200:
- id
- status
- updated_at

### POST /api/v1/error-groups/{group_id}/analyze (developer, admin)

Request:
- provider optional (mock or openai_compatible)
- force optional boolean

Response 202:
- analysis_job_id
- status

## 7. Analytics Endpoint

### GET /api/v1/analytics/summary (developer, admin)

Response 200:
- total_logs
- errors_last_24h
- errors_by_service
- errors_by_environment
- errors_by_severity
- most_frequent_error_groups
- unresolved_error_count
- avg_occurrences_per_group
- generated_at

## 8. System Endpoints

### GET /health (public)

Response 200:
- status: ok

### GET /ready (public)

Checks DB and Redis connectivity.

Response 200:
- status: ready
- checks: db, redis

Response 503 if any dependency unavailable.

### GET /metrics (public or protected by network policy)

Response:
- Prometheus text format

## 9. Validation and Limits

- Request body max size enforced by middleware.
- Bulk batch maximum configured with environment variable.
- Timestamp must be timezone-aware and reasonable range.
- Allowed enums strictly validated.

## 10. Rate Limits (initial defaults)

- Auth endpoints: strict per IP limits.
- Implemented baseline: Redis-backed login attempt limiter keyed by client IP and email.
- If Redis is unavailable, login throttling fails open so authentication remains available.
- Ingestion endpoints: per user and per IP burst limits.
- Read endpoints: moderate limits.
- Admin mutations: tighter limits.

Returned headers:
- X-RateLimit-Limit
- X-RateLimit-Remaining
- X-RateLimit-Reset

## 11. OpenAPI Conventions

- All endpoints have typed request/response schemas.
- Shared error schema documented.
- Security scheme: HTTP bearer JWT.
- Operation tags: auth, logs, error-groups, analytics, system.

## 12. Phase 4 Addendum

### POST /api/v1/logs/bulk (developer, admin)

Behavior:
- Creates a background ingestion job.
- Returns immediately with `202 Accepted`.
- Work is processed asynchronously by Celery worker.

Response 202:
- job_id
- status (`pending`)

### GET /api/v1/jobs/{job_id} (developer, admin)

Response 200:
- job_id
- status (`pending|running|completed|partially_completed|failed`)
- total_items
- processed_items
- success_count
- failure_count
- created_at
- started_at optional
- completed_at optional
- error_summary optional

### POST /api/v1/error-groups/{group_id}/analyze (developer, admin)

Behavior:
- Creates an analysis background job for a specific error group.
- Returns `202 Accepted` with `job_id`.

### GET /api/v1/error-groups/{group_id}/analysis (developer, admin)

Response 200:
- latest analysis record for group

Response 404:
- no analysis exists yet

### GET /api/v1/error-groups/{group_id}/analyses (developer, admin)

Response 200:
- analysis history list ordered newest first
