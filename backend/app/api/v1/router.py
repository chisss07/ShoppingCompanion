"""
API v1 main router.

All feature routers are included here with their sub-prefixes.
The top-level prefix /api/v1 is applied when this router is mounted
in app/main.py.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import health, history, search

# Root v1 router — prefix applied in main.py when mounting
api_v1_router = APIRouter()

# ── Search ──────────────────────────────────────────────────────────────────
# Endpoints: POST/GET /api/v1/search, GET/POST /api/v1/search/{id}/...
api_v1_router.include_router(search.router)

# ── History ─────────────────────────────────────────────────────────────────
# Endpoints: GET/DELETE /api/v1/history, DELETE /api/v1/history/{id}
api_v1_router.include_router(history.router)

# ── Sources meta endpoint ────────────────────────────────────────────────────
# GET /api/v1/sources is defined directly in health.py and
# registered on the main app in main.py so the /health route
# (which has no /api/v1 prefix) is also reachable.
# We include health here only for the /api/v1/sources route.
api_v1_router.include_router(health.router)
