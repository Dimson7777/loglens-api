# Environment Variables

## 1. Core Application

- APP_NAME: LogLens API
- APP_ENV: development | staging | production
- APP_DEBUG: true/false
- API_V1_PREFIX: /api/v1
- LOG_LEVEL: DEBUG | INFO | WARNING | ERROR
- JSON_LOGS: true/false
- CORS_ALLOW_ORIGINS: comma-separated origins
- MAX_REQUEST_SIZE_BYTES: maximum HTTP body size

## 2. Security and Auth

- JWT_SECRET_KEY: required strong secret
- JWT_ACCESS_SECRET_KEY: optional separate signing secret for access tokens
- JWT_REFRESH_SECRET_KEY: optional separate signing secret for refresh tokens
- JWT_ALGORITHM: HS256 (or configured algorithm)
- JWT_ACCESS_TOKEN_EXPIRE_MINUTES: integer
- JWT_REFRESH_TOKEN_EXPIRE_MINUTES: integer
- LOGIN_RATE_LIMIT_ATTEMPTS: integer login attempts allowed in window
- LOGIN_RATE_LIMIT_WINDOW_SECONDS: rolling window size in seconds
- PASSWORD_HASH_SCHEME: argon2 (implemented)
- ADMIN_BOOTSTRAP_EMAIL: optional initial admin email
- ADMIN_BOOTSTRAP_PASSWORD: optional initial admin password (local/dev only)

Notes:
- JWT_SECRET_KEY must be at least 32 characters.
- Do not commit real secrets to source control.

## 3. Database

- POSTGRES_HOST
- POSTGRES_PORT
- POSTGRES_DB
- POSTGRES_USER
- POSTGRES_PASSWORD
- DATABASE_URL: async SQLAlchemy URL (postgresql+asyncpg://...)
- ALEMBIC_DATABASE_URL: sync URL for migrations (postgresql+psycopg://...)

## 4. Redis and Celery

- REDIS_HOST
- REDIS_PORT
- REDIS_PASSWORD (optional)
- REDIS_URL
- CELERY_BROKER_URL
- CELERY_RESULT_BACKEND
- CELERY_TASK_MAX_RETRIES
- CELERY_TASK_RETRY_BACKOFF_BASE_SECONDS
- CELERY_TASK_RETRY_BACKOFF_MAX_SECONDS

## 5. Ingestion and Processing Limits

- LOG_BULK_MAX_ITEMS
- LOG_INGESTION_RATE_LIMIT_PER_MIN
- AUTH_RATE_LIMIT_PER_MIN
- READ_RATE_LIMIT_PER_MIN
- CLEANUP_RETENTION_DAYS

## 6. AI Provider

- AI_PROVIDER: mock | openai_compatible
- AI_TIMEOUT_SECONDS
- AI_MAX_INPUT_CHARS
- AI_OPENAI_BASE_URL: optional for compatible provider
- AI_OPENAI_API_KEY: optional, never committed
- AI_OPENAI_MODEL: model name

## 7. Metrics and Health

- METRICS_ENABLED: true/false
- READY_CHECK_TIMEOUT_SECONDS

## 8. Testing

- TEST_DATABASE_URL
- TEST_REDIS_URL

## 9. Example .env Guidance

- Keep .env.example populated with non-secret placeholders.
- Validate required variables at startup using typed settings.
- Fail fast on missing required production variables.
- Use a secret manager or deployment secret store for JWT and bootstrap credentials in production.

## 10. Phase 4 Variables (Implemented)

Celery and queues:
- CELERY_BROKER_URL
- CELERY_RESULT_BACKEND
- CELERY_TASK_ALWAYS_EAGER
- CELERY_TASK_HARD_TIME_LIMIT_SECONDS
- CELERY_TASK_SOFT_TIME_LIMIT_SECONDS
- CELERY_DEFAULT_QUEUE

AI analysis:
- AI_PROVIDER (`mock` or `openai_compatible`)
- AI_MODEL
- AI_REQUEST_TIMEOUT_SECONDS
- AI_MAX_INPUT_CHARS
- AI_MAX_STACK_TRACE_CHARS
- AI_OPENAI_BASE_URL (required for openai_compatible provider)
- AI_OPENAI_API_KEY (required for openai_compatible provider)

Maintenance and analytics:
- LOG_RETENTION_DAYS
- CLEANUP_BATCH_SIZE
- CLEANUP_DRY_RUN_DEFAULT
- ANALYTICS_CACHE_TTL_SECONDS

Host-based migration/testing tips:
- Set `ALEMBIC_DATABASE_URL` to localhost when running migrations outside Docker network.
- Set `DATABASE_URL`/`REDIS_URL` to localhost in host-run test sessions.
