"""
Application configuration loaded from environment variables.

All settings are validated by Pydantic on startup. Missing required
variables raise a clear error before the server accepts any traffic.

Usage:
    from app.core.config import get_settings
    settings = get_settings()
"""

from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central settings class.  All values are read from environment variables
    (or a .env file when running locally).  Variable names are
    case-insensitive by Pydantic convention.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        # Extra env vars that are not declared here are silently ignored so
        # that Docker Compose can inject Postgres / Redis config without
        # causing validation errors.
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────────
    APP_ENV: str = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    SECRET_KEY: str = "change-me-to-a-random-64-char-string"

    # ── Database — individual components so special chars in passwords work ──
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "shopping"
    POSTGRES_PASSWORD: str = "changeme"
    POSTGRES_DB: str = "shoppingcompanion"

    @property
    def DATABASE_URL(self) -> str:  # noqa: N802
        """Build the asyncpg URL using URL.create() so the password is
        properly percent-encoded regardless of what characters it contains."""
        from sqlalchemy.engine import URL
        return str(
            URL.create(
                "postgresql+asyncpg",
                username=self.POSTGRES_USER,
                password=self.POSTGRES_PASSWORD,
                host=self.POSTGRES_HOST,
                port=self.POSTGRES_PORT,
                database=self.POSTGRES_DB,
            )
        )

    # ── Redis ────────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Celery ───────────────────────────────────────────────────────────────
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ── Anthropic ────────────────────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = ""

    # ── CORS ─────────────────────────────────────────────────────────────────
    # Comma-separated string in the env file; parsed into a list below.
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:80"

    # ── Rate limiting ────────────────────────────────────────────────────────
    SEARCH_RATE_LIMIT_PER_MINUTE: int = 10
    SEARCH_RATE_LIMIT_PER_DAY: int = 200

    # ── External shopping APIs ───────────────────────────────────────────────
    AMAZON_ACCESS_KEY: str = ""
    AMAZON_SECRET_KEY: str = ""
    AMAZON_PARTNER_TAG: str = ""
    BESTBUY_API_KEY: str = ""
    WALMART_CONSUMER_ID: str = ""
    WALMART_PRIVATE_KEY: str = ""
    SERPAPI_KEY: str = ""
    EBAY_APP_ID: str = ""
    EBAY_CERT_ID: str = ""
    EBAY_OAUTH_TOKEN: str = ""

    # ── Playwright ───────────────────────────────────────────────────────────
    PLAYWRIGHT_WS_ENDPOINT: str = "ws://playwright:3000"

    # ── Derived helpers ──────────────────────────────────────────────────────
    @property
    def allowed_origins_list(self) -> List[str]:
        """Return ALLOWED_ORIGINS as a proper list of origin strings."""
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

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
    process lifetime.  Call ``get_settings.cache_clear()`` in tests to
    force re-parsing with a different environment.
    """
    return Settings()
