"""
Worker application configuration loaded from environment variables.

All settings are validated by Pydantic on startup. Missing required
variables raise a clear error before any task is accepted.

Usage:
    from app.core.config import get_settings
    settings = get_settings()
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central settings for the Celery worker.

    All values are read from environment variables (or a .env file when running
    locally). Variable names are case-insensitive by Pydantic convention.
    Extra env vars injected by Docker Compose are silently ignored.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────────
    APP_ENV: str = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str = (
        "postgresql+asyncpg://shopping:changeme@localhost:5432/shoppingcompanion"
    )

    # ── Redis ────────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Celery ───────────────────────────────────────────────────────────────
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ── Anthropic ────────────────────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = ""

    # ── External Shopping APIs ───────────────────────────────────────────────
    AMAZON_ACCESS_KEY: str = ""
    AMAZON_SECRET_KEY: str = ""
    AMAZON_PARTNER_TAG: str = ""
    BESTBUY_API_KEY: str = ""
    WALMART_CONSUMER_ID: str = ""
    WALMART_PRIVATE_KEY: str = ""
    SERPAPI_KEY: str = ""
    EBAY_APP_ID: str = ""
    EBAY_OAUTH_TOKEN: str = ""

    # ── Derived helpers ──────────────────────────────────────────────────────
    @property
    def is_production(self) -> bool:
        """Return True when running in the production environment."""
        return self.APP_ENV.lower() == "production"

    @property
    def is_development(self) -> bool:
        """Return True when running in the development environment."""
        return self.APP_ENV.lower() == "development"

    # ── Validators ───────────────────────────────────────────────────────────
    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Ensure LOG_LEVEL is a recognised Python logging level."""
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in valid:
            raise ValueError(f"LOG_LEVEL must be one of {valid}, got {v!r}")
        return upper

    @field_validator("APP_ENV")
    @classmethod
    def validate_app_env(cls, v: str) -> str:
        """Ensure APP_ENV is one of the recognised deployment environments."""
        valid = {"development", "staging", "production", "test"}
        lower = v.lower()
        if lower not in valid:
            raise ValueError(f"APP_ENV must be one of {valid}, got {v!r}")
        return lower


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return the singleton Settings instance.

    lru_cache ensures the environment is parsed only once per process.
    Call ``get_settings.cache_clear()`` in tests to force re-parsing
    with a different environment.
    """
    return Settings()
