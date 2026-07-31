"""Tests for HTTP middleware and application wiring."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.core.logging import JsonFormatter, get_logger
from fastapi.testclient import TestClient


def test_request_logging_middleware_captures_requests(client: TestClient) -> None:
    """Every completed request emits a structured log record."""
    logger = get_logger("xdebug.http")
    records: list[dict[str, Any]] = []

    class CaptureHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(json.loads(JsonFormatter().format(record)))

    handler = CaptureHandler()
    logger.addHandler(handler)
    try:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
    finally:
        logger.removeHandler(handler)

    completed = [r for r in records if r["message"] == "request completed"]
    assert len(completed) == 1
    assert completed[0]["status"] == 200
    assert "duration_ms" in completed[0]
    assert completed[0]["context"]["method"] == "GET"
    assert completed[0]["context"]["path"] == "/api/v1/health"


def test_root_endpoint_present(client: TestClient) -> None:
    """The root path returns a minimal landing payload."""
    body = client.get("/").json()
    assert body["app"] == "XDebug API"
    assert body["docs"] == "/docs"


def test_api_prefix_is_configurable() -> None:
    """Routers are mounted under the configured prefix."""
    from app.core.config import Settings
    from app.main import create_app

    app = create_app(Settings(_env_file=None, api_prefix="/custom"))
    with TestClient(app) as test_client:
        response = test_client.get("/custom/health")
    assert response.status_code == 200
