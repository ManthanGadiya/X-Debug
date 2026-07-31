"""Shared pytest fixtures for the backend test suite."""

from __future__ import annotations

import pytest
from app.core.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient


@pytest.fixture()
def settings() -> Settings:
    """Return isolated test settings that never read a local ``.env``."""
    return Settings(_env_file=None, environment="test")


@pytest.fixture()
def client(settings: Settings) -> TestClient:
    """Return a TestClient bound to a freshly built application."""
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client
