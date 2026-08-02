# Docker Compose Plan

## 1. Services

app:
- Builds from Dockerfile.
- Runs FastAPI with reload for development.
- Depends on db and redis health checks.
- Exposes API port 8000.

db:
- PostgreSQL 16 image.
- Persistent named volume for data.
- Health check using pg_isready.

redis:
- Redis 7 image.
- Health check using redis-cli ping.

worker:
- Uses same image/build context as app.
- Runs Celery worker command.
- Depends on redis and db.

Optional future service:
- celery-beat for periodic scheduling if needed.

## 2. Networks and Volumes

- Single internal bridge network for all services.
- Named volume: postgres_data for DB persistence.

## 3. Environment Variables

- Shared environment file for app and worker.
- Service-specific variables for DB and Redis credentials/URLs.
- No secrets committed; .env.example only.

## 4. Startup and Readiness Strategy

- Compose health checks gate dependent service startup.
- Application startup validates DB connectivity and runs migration command in startup script or separate init step.

## 5. Development Experience

- Bind mount source into container for hot reload.
- Separate command targets for app and worker.
- Keep container user permissions simple for local dev.

## 6. Security and Reliability Considerations

- Avoid exposing db/redis ports externally unless required.
- Use restart policy for worker and app in local persistent sessions.
- Enforce request-size limits at application level.

## 7. Example Compose Responsibilities

app command:
- uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

worker command:
- celery -A app.workers.celery_app.celery worker -l info
