"""
Celery application factory.

This module must be importable by both:
  - The FastAPI backend (to call .delay() on tasks)
  - The Celery worker process (entry point: celery -A app.celery_app worker)

The app is configured from the same Settings class as the FastAPI app,
ensuring DATABASE_URL, REDIS_URL, and all secrets come from the environment.
"""

from __future__ import annotations

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "shopping_companion",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.search_tasks",
    ],
)

# ── Celery configuration ─────────────────────────────────────────────────────
celery_app.conf.update(
    # Serialization — JSON is safer than pickle (no arbitrary code execution)
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Timezone
    timezone="UTC",
    enable_utc=True,
    # Task routing: search tasks go to the 'search' queue so we can scale
    # workers independently.  Maintenance tasks go to 'default'.
    task_routes={
        "app.tasks.search_tasks.run_search": {"queue": "search"},
    },
    task_default_queue="default",
    # Reliability
    task_acks_late=True,          # Acknowledge only after task completes
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1, # One task per greenlet to avoid starvation
    # Result expiry (keep results for 1 hour for status polling)
    result_expires=3600,
    # Gevent pool compatibility
    worker_pool="gevent",
    # Soft/hard time limits (seconds)
    task_soft_time_limit=120,     # Warn at 2 minutes
    task_time_limit=180,          # Kill at 3 minutes
)
