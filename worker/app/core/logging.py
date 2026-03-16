"""
Structured logging configuration using structlog.

Call ``configure_logging()`` once at worker startup. After that, obtain
loggers with ``structlog.get_logger(__name__)``.
"""

from __future__ import annotations

import logging
import sys

import structlog

from app.core.config import get_settings


def configure_logging() -> None:
    """
    Configure structlog with JSON output suitable for production log
    aggregators (Datadog, CloudWatch, etc.) and human-readable output in
    development.
    """
    settings = get_settings()
    log_level = getattr(logging, settings.LOG_LEVEL, logging.INFO)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.is_production:
        # JSON for log aggregation pipelines
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        # Colourful console output for local development
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # Suppress noisy third-party loggers in production
    for noisy in ("httpx", "httpcore", "celery.utils.functional"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
