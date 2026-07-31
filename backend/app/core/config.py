"""Application configuration.

Settings are loaded from environment variables prefixed with ``XDEBUG_`` and
an optional ``.env`` file through pydantic-settings. Every value carries a safe
default so the backend can boot with zero configuration for local development.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the XDebug backend."""

    model_config = SettingsConfigDict(
        env_prefix="XDEBUG_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "XDebug API"
    environment: str = "development"
    debug: bool = False
    api_prefix: str = "/api/v1"

    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://localhost:3000"]
    )

    log_level: str = "INFO"

    # Storage layer endpoints (unused until the storage phase; kept here so the
    # development environment contract is explicit).
    database_url: str = "postgresql://xdebug:xdebug@localhost:5432/xdebug"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "xdebug"

    max_repository_size_mb: int = 200
    analysis_timeout_seconds: int = 300

    # Repository ingestion (Phase 2).
    workspace_dir: str = "./.xdebug-workspace"
    github_clone_timeout_seconds: int = 120


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()
