"""API route handlers, one module per resource."""

from app.api.routes import (
    analysis,
    explanation,
    health,
    knowledge,
    localization,
    projects,
    runtime,
    tests,
)

__all__ = [
    "analysis",
    "explanation",
    "health",
    "knowledge",
    "localization",
    "projects",
    "runtime",
    "tests",
]
