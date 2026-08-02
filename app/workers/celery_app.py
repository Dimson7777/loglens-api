from __future__ import annotations

from celery import Celery

from app.core.config import get_settings
from app.observability.celery import setup_celery_observability

settings = get_settings()

celery_app = Celery(
    "loglens",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    task_default_queue=settings.celery_default_queue,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    task_always_eager=settings.celery_task_always_eager,
    task_eager_propagates=True,
    result_expires=86_400,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_routes={
        "app.workers.tasks.log_tasks.*": {"queue": "loglens.logs"},
        "app.workers.tasks.analysis_tasks.*": {"queue": "loglens.analysis"},
        "app.workers.tasks.cleanup_tasks.*": {"queue": "loglens.maintenance"},
        "app.workers.tasks.analytics_tasks.*": {"queue": "loglens.analytics"},
    },
    beat_schedule={
        "cleanup-old-logs-daily": {
            "task": "app.workers.tasks.cleanup_tasks.cleanup_old_logs_task",
            "schedule": 60.0 * 60.0 * 24.0,
            "kwargs": {"dry_run": settings.cleanup_dry_run_default},
        },
        "recalculate-analytics": {
            "task": "app.workers.tasks.analytics_tasks.recalculate_summary_analytics_task",
            "schedule": 60.0 * 5.0,
        },
    },
)

celery_app.autodiscover_tasks(["app.workers.tasks"])
setup_celery_observability(celery_app, settings)
