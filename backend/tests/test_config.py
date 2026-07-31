"""Tests for configuration loading and environment overrides."""

from __future__ import annotations

from app.core.config import Settings


def test_settings_defaults() -> None:
    """Defaults boot the backend with zero configuration."""
    settings = Settings(_env_file=None)
    assert settings.environment == "development"
    assert settings.api_prefix == "/api/v1"
    assert settings.max_repository_size_mb == 200
    assert settings.analysis_timeout_seconds == 300
    assert settings.cors_origins == ["http://localhost:5173", "http://localhost:3000"]


def test_settings_from_environment(monkeypatch) -> None:
    """Environment variables override defaults through the XDEBUG_ prefix."""
    monkeypatch.setenv("XDEBUG_ENVIRONMENT", "production")
    monkeypatch.setenv("XDEBUG_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("XDEBUG_DEBUG", "true")

    settings = Settings(_env_file=None)
    assert settings.environment == "production"
    assert settings.log_level == "DEBUG"
    assert settings.debug is True


def test_settings_ignore_unknown_environment_variables(monkeypatch) -> None:
    """Unknown XDEBUG_ variables do not break instantiation."""
    monkeypatch.setenv("XDEBUG_SOMETHING_ELSE", "1")
    settings = Settings(_env_file=None)
    assert settings.app_name == "XDebug API"
