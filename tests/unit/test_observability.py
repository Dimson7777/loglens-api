from __future__ import annotations

from collections.abc import Generator

import pytest

from app.core.config import Settings
from app.observability import sentry as sentry_module
from app.observability import tracing as tracing_module
from app.observability.metrics import (
    APPLICATION_ERRORS_TOTAL,
    HTTP_REQUESTS_TOTAL,
    increment_application_error,
    observe_http_request,
)


def test_http_request_metric_increments() -> None:
    metric = HTTP_REQUESTS_TOTAL.labels(method="GET", path="/health", status_code="200")
    before = metric._value.get()  # type: ignore[attr-defined]

    observe_http_request("GET", "/health", 200, 0.012)

    after = metric._value.get()  # type: ignore[attr-defined]
    assert after == before + 1


def test_application_error_metric_increments() -> None:
    metric = APPLICATION_ERRORS_TOTAL.labels(error_type="RuntimeError", path="/api/v1/logs")
    before = metric._value.get()  # type: ignore[attr-defined]

    increment_application_error("RuntimeError", "/api/v1/logs")

    after = metric._value.get()  # type: ignore[attr-defined]
    assert after == before + 1


def test_otlp_header_parser() -> None:
    headers = tracing_module._parse_otlp_headers("Authorization=Bearer xyz, x-tenant = abc")
    assert headers == {"Authorization": "Bearer xyz", "x-tenant": "abc"}


@pytest.fixture
def reset_sentry_flag() -> Generator[None, None, None]:
    original = sentry_module._SENTRY_CONFIGURED
    sentry_module._SENTRY_CONFIGURED = False
    try:
        yield
    finally:
        sentry_module._SENTRY_CONFIGURED = original


def test_sentry_setup_is_noop_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
    reset_sentry_flag: None,
) -> None:
    called = {"value": False}

    def _fake_init(*args: object, **kwargs: object) -> None:
        del args, kwargs
        called["value"] = True

    monkeypatch.setattr(sentry_module.sentry_sdk, "init", _fake_init)

    settings = Settings(
        sentry_enabled=False,
        sentry_dsn=None,
        jwt_secret_key="test-jwt-secret-key-with-at-least-32-characters",
    )
    sentry_module.setup_sentry(settings)
    assert called["value"] is False


def test_production_config_rejects_default_jwt_secret() -> None:
    with pytest.raises(ValueError, match="non-default"):
        Settings(
            app_env="production",
            app_debug=False,
            jwt_secret_key="dev-only-change-this-jwt-secret-key-to-a-strong-value",
        )


def test_production_config_rejects_debug_mode() -> None:
    with pytest.raises(ValueError, match="APP_DEBUG must be false"):
        Settings(
            app_env="production",
            app_debug=True,
            jwt_secret_key="this-is-a-long-production-secret-key-32-characters",
        )


def test_sentry_enabled_requires_dsn() -> None:
    with pytest.raises(ValueError, match="SENTRY_DSN"):
        Settings(
            sentry_enabled=True,
            sentry_dsn=None,
            jwt_secret_key="test-jwt-secret-key-with-at-least-32-characters",
        )
