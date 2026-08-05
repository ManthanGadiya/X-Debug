"""Application configuration.

Settings are loaded from environment variables prefixed with ``XDEBUG_`` and
an optional ``.env`` file through pydantic-settings. Every value carries a safe
default so the backend can boot with zero configuration for local development.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repository root anchors the default workspace. The workspace holds cloned and
# uploaded repositories (plus analysis artifacts) that change constantly, so
# defaulting it below ``backend/`` would sit inside uvicorn's ``--reload`` watch
# dir and restart the dev server on every clone. Anchoring it to the repo root
# keeps those writes out of the watched tree regardless of the launch flags.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_WORKSPACE_DIR = str(_REPO_ROOT / ".xdebug-workspace")


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

    # Static analysis performance (Phase 9).
    analysis_cache_capacity: int = 2048
    # Threads used to parse source files concurrently. 0 selects a sensible
    # default (min(32, cpu_count + 4)); 1 disables parallelism.
    analysis_max_workers: int = 0

    # Repository ingestion (Phase 2).
    workspace_dir: str = _DEFAULT_WORKSPACE_DIR
    github_clone_timeout_seconds: int = 120

    # Runtime execution (Phase 4).
    runtime_timeout_seconds: int = 60
    max_output_chars: int = 50_000
    max_trace_events: int = 10_000
    c_compiler: str = "gcc"
    cpp_compiler: str = "g++"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()
