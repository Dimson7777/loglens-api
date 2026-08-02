# pyproject.toml Dependency Plan

## 1. Python Version

- Requires Python >= 3.12 and < 3.13

## 2. Runtime Dependencies

Web and API:
- fastapi
- uvicorn[standard]
- pydantic
- pydantic-settings

Database:
- sqlalchemy
- asyncpg
- alembic

Auth and security:
- pyjwt
- pwdlib (or passlib with bcrypt)

Background jobs and redis:
- celery
- redis

Observability and utilities:
- prometheus-fastapi-instrumentator
- structlog
- orjson
- python-multipart

Optional AI provider:
- httpx

## 3. Development Dependencies

Testing:
- pytest
- pytest-asyncio
- pytest-cov
- anyio
- faker

Lint/format/type:
- ruff
- mypy
- types-redis

Pre-commit:
- pre-commit

## 4. Suggested pyproject Tool Configuration

Ruff:
- Enable lint rules: E, F, I, B, UP, N, C4, SIM
- Set line length to 100
- Enforce import sorting

Mypy:
- strict = true
- warn_unused_ignores = true
- disallow_untyped_defs = true
- no_implicit_optional = true
- plugins for pydantic if needed

Pytest:
- testpaths = tests
- asyncio_mode = auto
- addopts includes strict markers and summary flags

## 5. Dependency Rationale Highlights

- SQLAlchemy async + asyncpg provides production-grade PostgreSQL support.
- Celery + Redis is operationally simple and widely supported.
- Structlog improves machine-readable logs and correlation metadata.
- Prometheus instrumentation enables ready metrics exposure.

## 6. Packaging Notes

- Use editable install for local dev.
- Keep dependency versions constrained to compatible major/minor ranges.
- Separate optional extras for ai-openai and dev.
