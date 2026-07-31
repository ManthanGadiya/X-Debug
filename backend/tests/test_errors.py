"""Tests for structured errors and the HTTP error envelope."""

from __future__ import annotations

from app.core.config import Settings
from app.core.errors import AnalysisError, NotFoundError, XDebugError
from app.main import create_app
from fastapi.testclient import TestClient


def test_error_envelope_matches_architecture() -> None:
    """Errors serialize to the documented envelope shape."""
    err = AnalysisError("Syntax Error", module="CFG Builder", file="main.py", line=45)
    assert err.to_dict() == {
        "status": "error",
        "module": "CFG Builder",
        "reason": "Syntax Error",
        "file": "main.py",
        "line": 45,
    }


def test_subclass_default_reason() -> None:
    """Concrete error types provide a default reason when none is given."""
    assert NotFoundError().reason == "Resource not found"
    assert XDebugError().reason == "Internal error"


def test_error_handler_returns_structured_response(settings: Settings) -> None:
    """Raised XDebugError instances reach the client as structured JSON."""
    app = create_app(settings)

    @app.get("/boom")
    async def boom() -> None:
        raise AnalysisError("boom", module="test-module")

    with TestClient(app) as test_client:
        response = test_client.get("/boom")

    assert response.status_code == 500
    body = response.json()
    assert body == {"status": "error", "module": "test-module", "reason": "boom"}
