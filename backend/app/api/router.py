"""API router aggregation.

All resource routers are mounted here under the application-wide prefix
configured in ``Settings.api_prefix`` (``/api/v1`` by default).
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import health

api_router = APIRouter()
api_router.include_router(health.router)
