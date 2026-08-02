from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import EmailStr, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "LogLens API"
    app_env: Literal["development", "staging", "production"] = "development"
    app_debug: bool = False
    api_v1_prefix: str = "/api/v1"

    log_level: str = "INFO"
    json_logs: bool = True
    metrics_enabled: bool = True
    metrics_path: str = "/metrics"

    otel_enabled: bool = False
    otel_service_name: str = "loglens-api"
    otel_sample_ratio: float = 1.0
    otel_exporter_otlp_endpoint: str | None = None
    otel_exporter_otlp_headers: str = ""
    otel_exporter_timeout_seconds: float = 10.0

    sentry_enabled: bool = False
    sentry_dsn: str | None = None
    sentry_traces_sample_rate: float = 0.0
    release_name: str = "loglens-api@0.1.0"

    cors_allow_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    max_request_size_bytes: int = 1_048_576
    ready_check_timeout_seconds: float = 2.0

    jwt_secret_key: str = "dev-only-change-this-jwt-secret-key-to-a-strong-value"
    jwt_access_secret_key: str | None = None
    jwt_refresh_secret_key: str | None = None
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_minutes: int = 10_080
    login_rate_limit_attempts: int = 5
    login_rate_limit_window_seconds: int = 60
    log_bulk_max_items: int = 100
    log_page_size_default: int = 20
    log_page_size_max: int = 100
    error_group_page_size_default: int = 20
    error_group_page_size_max: int = 100
    bulk_idempotency_ttl_seconds: int = 86_400
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/1"
    celery_task_hard_time_limit_seconds: int = 180
    celery_task_soft_time_limit_seconds: int = 150
    celery_default_queue: str = "loglens.default"
    celery_task_always_eager: bool = False

    ai_provider: Literal["mock", "openai_compatible"] = "mock"
    ai_model: str = "mock-gpt"
    ai_request_timeout_seconds: float = 15.0
    ai_max_input_chars: int = 20_000
    ai_max_stack_trace_chars: int = 8_000
    ai_openai_base_url: str | None = None
    ai_openai_api_key: str | None = None

    log_retention_days: int = 30
    cleanup_batch_size: int = 1_000
    cleanup_dry_run_default: bool = False
    analytics_cache_ttl_seconds: int = 300

    admin_bootstrap_email: EmailStr | None = None
    admin_bootstrap_password: str | None = None

    postgres_host: str = "db"
    postgres_port: int = 5432
    postgres_db: str = "loglens"
    postgres_user: str = "loglens"
    postgres_password: str = "loglens"

    database_url: str = "postgresql+asyncpg://loglens:loglens@db:5432/loglens"
    alembic_database_url: str = "postgresql+psycopg://loglens:loglens@db:5432/loglens"
    database_pool_size: int = 10
    database_max_overflow: int = 20
    database_pool_timeout_seconds: float = 30.0
    database_pool_recycle_seconds: int = 1800

    redis_url: str = "redis://redis:6379/0"
    redis_socket_timeout_seconds: float = 2.0
    redis_health_check_interval_seconds: int = 30

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def _parse_cors_allow_origins(cls, value: object) -> list[str] | object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("jwt_secret_key")
    @classmethod
    def _validate_jwt_secret_key(cls, value: str) -> str:
        if len(value) < 32:
            raise ValueError("JWT secret key must be at least 32 characters long.")
        return value

    @field_validator("jwt_access_secret_key", "jwt_refresh_secret_key")
    @classmethod
    def _validate_optional_jwt_secret_key(cls, value: str | None) -> str | None:
        if value is not None and len(value) < 32:
            raise ValueError("JWT secret key must be at least 32 characters long.")
        return value

    @field_validator("otel_sample_ratio", "sentry_traces_sample_rate")
    @classmethod
    def _validate_sample_rate(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError("Sample rate must be between 0 and 1.")
        return value

    @model_validator(mode="after")
    def _validate_production_settings(self) -> Settings:
        if self.metrics_enabled and not self.metrics_path.startswith("/"):
            raise ValueError("METRICS_PATH must start with '/'.")

        if self.sentry_enabled and not self.sentry_dsn:
            raise ValueError("SENTRY_DSN is required when SENTRY_ENABLED is true.")

        if self.app_env == "production":
            if self.app_debug:
                raise ValueError("APP_DEBUG must be false in production.")
            if self.jwt_secret_key == "dev-only-change-this-jwt-secret-key-to-a-strong-value":
                raise ValueError("JWT_SECRET_KEY must be set to a non-default value in production.")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
