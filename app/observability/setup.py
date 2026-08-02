from __future__ import annotations

from fastapi import FastAPI
from prometheus_client import make_asgi_app

from app.core.config import Settings
from app.observability.sentry import setup_sentry
from app.observability.tracing import setup_tracing


def setup_observability(app: FastAPI, settings: Settings) -> None:
    setup_sentry(settings)
    setup_tracing(app, settings)

    if settings.metrics_enabled:
        app.mount(settings.metrics_path, make_asgi_app())
