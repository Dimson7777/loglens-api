# LogLens API

LogLens API is a production-oriented FastAPI backend for ingesting and analyzing production application logs.

This repository currently implements Phase 2 foundation:
- Python 3.12 project initialization
- FastAPI app bootstrap
- Pydantic Settings-based configuration
- Structured JSON logging
- Async SQLAlchemy PostgreSQL wiring
- Redis connectivity wiring
- Alembic configuration
- Dockerfile and Docker Compose (API, PostgreSQL, Redis)
- Health and readiness endpoints
- Centralized exception handling
- Initial pytest integration tests
- User model with roles and active status
- JWT authentication (register, login, refresh, logout, logout-all, me)
- Admin user management endpoints
- Role-based authorization dependencies
- Redis-backed login rate limiting with fail-open behavior when Redis is unavailable
- Refresh-token rotation, family revocation, and reuse detection

## Tech Stack (Phase 2)

- Python 3.12
- FastAPI
- Pydantic v2 and pydantic-settings
- SQLAlchemy 2.0 async with asyncpg
- Alembic
- PostgreSQL
- Redis
- Ruff
- mypy (strict)
- pytest
- Docker and Docker Compose
- python-jose (JWT)
- argon2-cffi (password hashing)

## Project Layout

- app: application code
- migrations: Alembic config and migration scripts
- tests: integration and test fixtures
- scripts: development utilities (including admin seeding)

## Local Setup

1. Create and activate a virtual environment.
2. Install dependencies.
3. Copy environment configuration.

### PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .[dev]
Copy-Item .env.example .env
```

## Run the API Locally

```powershell
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Run with Docker Compose

```powershell
Copy-Item .env.example .env
docker compose up --build -d
docker compose ps
docker compose logs --tail=200
```

Install development tooling in the running API container:

```powershell
docker compose exec api pip install -e .[dev]
```

## Health Endpoints

- GET /health
- GET /ready

## Database Migrations

Create a migration:

```powershell
alembic revision --autogenerate -m "init"
```

Apply migrations:

```powershell
alembic upgrade head
```

Seed initial admin user (development only):

```powershell
$env:ADMIN_BOOTSTRAP_EMAIL="admin@example.com"
$env:ADMIN_BOOTSTRAP_PASSWORD="ChangeThisToAStrongPassword123"
python -m scripts.seed_admin_user
```

Production deployments should source `JWT_SECRET_KEY`, `JWT_ACCESS_SECRET_KEY`, `JWT_REFRESH_SECRET_KEY`,
and `ADMIN_BOOTSTRAP_PASSWORD` from a secret manager such as AWS Secrets Manager, Azure Key Vault, or
HashiCorp Vault rather than plain environment files.

Rollback one migration:

```powershell
alembic downgrade -1
```

## Quality and Test Commands

Exact verified sequence used in this workspace:

```powershell
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

If host Python is unavailable, run the equivalent checks in the API container:

```powershell
docker compose exec api python -m pip install --upgrade pip
docker compose exec api python -m pip install -e ".[dev]"
docker compose exec api ruff check .
docker compose exec api ruff format --check .
docker compose exec api mypy .
docker compose exec api pytest -v
docker compose ps
docker compose logs --tail=200
docker compose logs --since=5m --tail=200
```

## Auth and User Endpoints

- POST /api/v1/auth/register
- POST /api/v1/auth/login
- POST /api/v1/auth/refresh
- POST /api/v1/auth/logout
- POST /api/v1/auth/logout-all
- GET /api/v1/auth/me
- GET /api/v1/users (admin)
- PATCH /api/v1/users/{user_id}/role (admin)
- PATCH /api/v1/users/{user_id}/status (admin)

### Example curl Requests

Register:

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
	-H "Content-Type: application/json" \
	-d '{"email":"dev@example.com","password":"SuperSecurePass123"}'
```

Login:

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
	-H "Content-Type: application/json" \
	-d '{"email":"dev@example.com","password":"SuperSecurePass123"}'
```

Current user:

```bash
curl -X GET http://localhost:8000/api/v1/auth/me \
	-H "Authorization: Bearer <access_token>"
```

## Authorization Rules

- `require_authenticated_user`: any authenticated active user
- `require_developer_or_admin`: developer or admin user
- `require_admin_user`: admin only

Current implemented route protections:
- `/api/v1/users*` endpoints require admin

Refresh-token note:
- The current implementation returns refresh tokens in the JSON body for API clients.
- If you later move refresh tokens into `HttpOnly` cookies, add CSRF protection before enabling cookie-based refresh.

Designed permissions for upcoming log and analysis endpoints:
- developers can create and read logs
- developers can trigger AI analysis
- admins can delete logs
- admins can manage users
- admins can change error-group status

## Environment Variables

See .env.example for required settings.

## Next Steps

After Phase 2 approval, implementation proceeds with log ingestion and error-group workflows in Phase 3.

## Phase 4 Status

Phase 4 is implemented and validated in this workspace.

Implemented:
- Celery integration with Redis broker and result backend
- Async bulk ingestion via `POST /api/v1/logs/bulk` returning `202` + `job_id`
- Job status endpoint `GET /api/v1/jobs/{job_id}`
- Error-group analysis workflow:
	- `POST /api/v1/error-groups/{group_id}/analyze`
	- `GET /api/v1/error-groups/{group_id}/analysis`
	- `GET /api/v1/error-groups/{group_id}/analyses`
- AI provider abstraction (mock and OpenAI-compatible)
- Background maintenance tasks:
	- periodic cleanup of old logs
	- periodic analytics cache refresh

Validated sequence (host):
- `alembic upgrade head` (with `ALEMBIC_DATABASE_URL` override for localhost)
- `ruff check .`
- `ruff format --check .`
- `mypy .`
- `pytest -v` (41 passed)

Runtime verification (Docker Compose):
- API, DB, Redis, Celery worker, and Celery beat services start healthy.
- Bulk ingestion job reaches `completed` with expected counts.
- Error-group analysis job reaches `completed` and persists analysis output.
