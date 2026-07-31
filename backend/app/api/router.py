"""API router aggregation.

All resource routers are mounted here under the application-wide prefix
configured in ``Settings.api_prefix`` (``/api/v1`` by default).
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import analysis, health, knowledge, projects, runtime, tests

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(projects.router)
api_router.include_router(analysis.router)
api_router.include_router(runtime.router)
api_router.include_router(tests.router)
api_router.include_router(knowledge.router)
