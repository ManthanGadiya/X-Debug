"""Health check endpoints used for liveness and connectivity checks."""

from __future__ import annotations

from fastapi import APIRouter

from app import __version__
from app.container import ContainerDep
from app.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse, summary="Liveness check")
def health(container: ContainerDep) -> HealthResponse:
    """Return basic application information and confirm the API is alive."""
    settings = container.settings
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        version=__version__,
        environment=settings.environment,
    )
