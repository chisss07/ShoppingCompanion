"""
Structured logging configuration using structlog.

- Production: JSON output (one line per log event, machine-parseable)
- Development: colored, human-readable console output

Usage:
    from app.core.logging import get_logger
    logger = get_logger(__name__)
    logger.info("search_started", session_id=str(session_id), query=query)
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, WrappedLogger


def _add_severity_field(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """
    Rename structlog's internal 'level' key to 'severity' so log aggregators
    like Google Cloud Logging and Datadog pick it up correctly.
    """
    if "level" in event_dict:
        event_dict["severity"] = event_dict.pop("level").upper()
    return event_dict


def configure_logging(log_level: str = "INFO", is_production: bool = False) -> None:
    """
    Configure the structlog and stdlib logging pipelines.

    This must be called once, early in application startup (lifespan), before
    any logger is used.

    Args:
        log_level:     One of DEBUG, INFO, WARNING, ERROR, CRITICAL.
        is_production: When True, JSON rendering is used. When False, colored
                       console rendering is used.
    """
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if is_production:
        # JSON output for log aggregation pipelines
        processors = [
            *shared_processors,
            _add_severity_field,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
        renderer: Any = structlog.processors.JSONRenderer()
    else:
        # Human-friendly colored output for local development
        processors = [
            *shared_processors,
            structlog.dev.ConsoleRenderer(colors=True),
        ]
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(log_level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Also configure the standard library logging so that third-party
    # libraries (SQLAlchemy, uvicorn, httpx) emit their logs through
    # structlog instead of bypassing it.
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.getLevelName(log_level.upper()),
    )

    # Reduce noise from chatty libraries
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.DEBUG if log_level.upper() == "DEBUG" else logging.WARNING
    )
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str = __name__) -> structlog.BoundLogger:
    """
    Return a structlog BoundLogger bound to the given name.

    Args:
        name: Typically ``__name__`` of the calling module.

    Returns:
        A structlog BoundLogger ready for use.
    """
    return structlog.get_logger(name)
