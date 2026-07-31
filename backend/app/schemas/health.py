"""Pydantic response schemas for the health endpoint."""

from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Liveness payload returned by ``GET /health``."""

    status: str
    app: str
    version: str
    environment: str
