"""
Celery application factory.

Import this module to obtain the configured Celery app instance:

    from app.celery_app import app

The module is intentionally kept thin — all business logic lives in tasks
and services so this file can be imported cheaply for beat scheduling.
"""

from __future__ import annotations

from celery import Celery
from celery.signals import worker_process_init

from app.core.config import get_settings

settings = get_settings()

app = Celery(
    "shopping_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.search_tasks",
        "app.tasks.maintenance_tasks",
    ],
)

app.conf.update(
    # Serialisation
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Timezone
    timezone="UTC",
    enable_utc=True,
    # Routing: all search tasks go to the dedicated "search" queue
    task_routes={
        "app.tasks.search_tasks.*": {"queue": "search"},
        "app.tasks.maintenance_tasks.*": {"queue": "default"},
    },
    # Time limits: hard-kill at 120 s, raise SoftTimeLimitExceeded at 90 s
    task_time_limit=120,
    task_soft_time_limit=90,
    # Result expiry — keep task results for 24 hours
    result_expires=86400,
    # Acks are sent after the task finishes so a crashed worker re-queues
    task_acks_late=True,
    # Reject (re-queue) on worker power loss, not on task exception
    task_reject_on_worker_lost=True,
    # Beat schedule (used when running celery beat)
    beat_schedule={
        "check-source-health-every-5-minutes": {
            "task": "app.tasks.maintenance_tasks.check_source_health",
            "schedule": 300,  # seconds
            "options": {"queue": "default"},
        },
        "clean-old-sessions-daily": {
            "task": "app.tasks.maintenance_tasks.clean_old_sessions",
            "schedule": 86400,  # seconds
            "options": {"queue": "default"},
        },
    },
    # RedBeat scheduler storage key prefix
    redbeat_redis_url=settings.REDIS_URL,
    redbeat_key_prefix="redbeat:",
)


@worker_process_init.connect
def init_worker_process(**_kwargs: object) -> None:
    """Initialise per-process resources (logging) when a worker process forks."""
    from app.core.logging import configure_logging

    configure_logging()
