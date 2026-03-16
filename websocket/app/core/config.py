"""
WebSocket server configuration loaded from environment variables.

All settings are validated by Pydantic on startup. Missing required
variables raise a clear error before the server accepts any traffic.

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
    Central settings for the WebSocket server.

    Values are read from environment variables or a .env file when running
    locally. Extra variables injected by Docker Compose (e.g. Postgres
    credentials intended for other services) are silently ignored so the
    same .env file can be shared across the whole stack.
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

    # ── Redis ────────────────────────────────────────────────────────────────
    # The WebSocket server only needs the general-purpose Redis database; it
    # does not interact with Celery's broker or result-backend databases.
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Derived helpers ──────────────────────────────────────────────────────
    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"

    @property
    def is_development(self) -> bool:
        return self.APP_ENV.lower() == "development"

    # ── Validators ───────────────────────────────────────────────────────────
    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in valid:
            raise ValueError(f"LOG_LEVEL must be one of {valid}, got {v!r}")
        return upper

    @field_validator("APP_ENV")
    @classmethod
    def validate_app_env(cls, v: str) -> str:
        valid = {"development", "staging", "production", "test"}
        lower = v.lower()
        if lower not in valid:
            raise ValueError(f"APP_ENV must be one of {valid}, got {v!r}")
        return lower


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return the singleton Settings instance.

    lru_cache ensures the environment is parsed only once across the entire
    process lifetime. Call ``get_settings.cache_clear()`` in tests to force
    re-parsing with a different environment.
    """
    return Settings()
