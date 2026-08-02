# LogLens API Architecture

## 1. Goals and Scope

LogLens API is a backend service for ingesting, storing, searching, grouping, and analyzing production logs.

Primary goals:
- Reliable ingestion for single and bulk logs.
- Deterministic error grouping via fingerprints.
- Queryable log and error-group data with pagination and filtering.
- Async background processing for heavy or delayed work.
- Secure, role-based API with production-friendly defaults.
- Clean, testable architecture suitable for local development and CI.

Out of scope in initial implementation:
- Real-time streaming pipelines (Kafka, Pulsar).
- Multi-tenant billing and usage quotas.
- Advanced anomaly detection ML pipelines.

## 2. Architectural Style

Pattern: Layered Clean Architecture (modular monolith)

Layers:
- API layer: FastAPI routes, request parsing, response serialization, auth/permission checks.
- Service layer: business logic, orchestration, transactions.
- Repository layer: SQLAlchemy query and persistence logic.
- Domain and schema layer: typed entities/enums and Pydantic v2 schemas.
- Infrastructure layer: PostgreSQL, Redis, Celery, AI provider integrations, logging, metrics.

Why this choice:
- Keeps business logic out of route handlers.
- Supports easier testing through dependency injection and clear seams.
- Avoids microservice overhead while still preserving modular boundaries.

## 3. Runtime Components

Core components:
- FastAPI application (async endpoints).
- PostgreSQL for durable relational storage.
- Redis for Celery broker/result backend and short-lived cache/rate-limit support.
- Celery worker for background tasks.
- Optional OpenAI-compatible provider for AI analysis; mock provider for local and tests.

Component responsibilities:
- API app handles synchronous validation and minimal request-time persistence.
- Celery handles non-blocking workloads such as bulk processing and analysis.
- DB stores canonical log, group, user, and analysis records.

Implemented in Phase 2:
- User management with SQLAlchemy `User` model and role enum (`admin`, `developer`).
- Auth service for registration and login with Argon2 password hashing.
- JWT access token generation and verification.
- Repository and service layers for user/auth operations.
- Reusable authorization dependencies:
	- authenticated users
	- admin-only routes
	- developer-or-admin routes

## 4. Data and Control Flow

Authentication flow:
1. Register validates email/password and checks duplicates.
2. Password is hashed with Argon2 and persisted.
3. Login applies rate limiting, verifies credentials, checks active status.
4. API returns JWT access token with expiration.
5. Protected routes decode token and load current user via dependency injection.

Single log ingestion:
1. Authenticated caller sends log payload.
2. API validates payload and request size.
3. Service normalizes content and computes deterministic fingerprint.
4. Repository writes log and upserts corresponding error group in one transaction.
5. API returns accepted resource.

Bulk ingestion:
1. API validates batch boundaries and caller permissions.
2. API stores a job request and enqueues Celery task.
3. Worker processes logs in idempotent chunks with retry/backoff.
4. Worker writes logs and updates groups transactionally per chunk.

AI analysis:
1. Caller triggers analysis for one error group.
2. API enqueues job or performs fast-path sync dispatch for mock provider.
3. Worker fetches representative logs and context.
4. Provider returns structured JSON.
5. Pydantic validates response and persists analysis record.

## 5. Cross-Cutting Concerns

Dependency injection:
- FastAPI dependency functions provide DB sessions, current user, permissions, and service instances.
- Provider interfaces (AI, fingerprint strategy) injected into services for testability.

Error handling:
- Centralized exception mapping in global handlers.
- Domain exceptions mapped to consistent error envelopes.
- Internal details suppressed from external responses.

Structured logging:
- JSON logs with request_id, user_id, route, status_code, latency_ms.
- Worker logs include task_id, retry_count, job_type.

Observability:
- Health endpoint for process liveness.
- Readiness endpoint checks DB and Redis availability.
- Prometheus metrics endpoint for HTTP and task counters/histograms.

Security:
- JWT auth with role-based authorization.
- Password hashing with Argon2/bcrypt policy.
- Rate limiting by user/IP and endpoint class.
- CORS allow-list and maximum request-size middleware.

## 6. Key Engineering Decisions

Decision: Async SQLAlchemy sessions with PostgreSQL only.
- Rationale: aligns with FastAPI async model and production-like I/O behavior.

Decision: Deterministic fingerprint persisted on every log.
- Rationale: enables fast group lookups and consistent aggregation.

Decision: Celery for deferred processing.
- Rationale: straightforward retries/backoff and broad operational familiarity.

Decision: Mock AI provider as first-class implementation.
- Rationale: enables deterministic tests and local development without secrets.

Decision: Modular monolith over microservices.
- Rationale: lowers complexity and deployment overhead while preserving clear boundaries.

## 7. Scalability and Performance Considerations

- Add indexes for primary filter dimensions and time windows.
- Use cursor or offset-limit pagination with validated sort fields.
- Keep bulk processing chunked to control memory and lock contention.
- Denormalize light aggregates in error_groups for fast dashboards.
- Avoid N+1 by explicit joins/selectin loading where required.

## 8. Reliability Model

- Idempotency keys for bulk ingestion requests.
- Celery tasks with retry policy and exponential backoff.
- Dead-letter handling strategy via max retries and failure state records.
- Transaction boundaries around log insert plus group update.

## 9. Evolution Path

Later enhancements:
- S3/archive tier for long-term log retention.
- Webhook or event streaming for alerting integrations.
- Fine-grained ABAC permissions and organization scoping.
- Advanced anomaly and trend detection jobs.

## 10. Phase 4 Addendum

Background job model:
- `background_jobs` table tracks long-running operations with status and progress counters.
- `error_analyses` table stores AI-generated analysis history with provider metadata.
- Job status lifecycle: `pending -> running -> completed|partially_completed|failed`.

Task execution:
- API endpoints enqueue Celery tasks in normal runtime.
- Test/runtime eager mode executes task logic inline.
- Inline eager paths now reuse the request-scoped SQLAlchemy session to avoid cross-event-loop asyncpg issues on Windows.

Maintenance scheduling:
- Celery beat schedules cleanup and analytics tasks.
- Cleanup uses batched deletes with optional dry-run count mode.
- Analytics task computes aggregate metrics and caches payload in Redis with TTL.
