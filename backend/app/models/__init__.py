# ORM model classes — imported here so Alembic autogenerate discovers them
from app.models.auth import AdminUser, AppSetting  # noqa: F401
from app.models.search import (  # noqa: F401
    AlternativeProduct,
    SearchResult,
    SearchSession,
    SearchSummary,
)
