from __future__ import annotations

from typing import Any

import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.fastapi import FastApiIntegration

from app.core.config import Settings

_SENTRY_CONFIGURED = False


def _before_send(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
    del hint
    request_data = event.get("request")
    if isinstance(request_data, dict):
        request_data.pop("cookies", None)
        headers = request_data.get("headers")
        if isinstance(headers, dict):
            headers.pop("authorization", None)
            headers.pop("cookie", None)
    user_data = event.get("user")
    if isinstance(user_data, dict):
        user_data.pop("email", None)
        user_data.pop("ip_address", None)
    return event


def setup_sentry(settings: Settings) -> None:
    global _SENTRY_CONFIGURED
    if _SENTRY_CONFIGURED or not settings.sentry_enabled or not settings.sentry_dsn:
        return

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        release=settings.release_name,
        send_default_pii=False,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        before_send=_before_send,
        integrations=[
            FastApiIntegration(transaction_style="url"),
            CeleryIntegration(monitor_beat_tasks=True),
        ],
    )
    sentry_sdk.set_tag("service", settings.otel_service_name)
    _SENTRY_CONFIGURED = True
