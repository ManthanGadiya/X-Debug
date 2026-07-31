"""Tests for the health endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    """The health endpoint reports a live application with metadata."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "ok"
    assert body["app"] == "XDebug API"
    assert body["environment"] == "test"
    assert body["version"]


def test_health_does_not_expose_debug_info(client: TestClient) -> None:
    """The health payload contains no internal or secret fields."""
    body = client.get("/api/v1/health").json()
    assert set(body.keys()) == {"status", "app", "version", "environment"}
