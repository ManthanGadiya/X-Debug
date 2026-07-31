"""Dependency injection.

The application factory builds a :class:`Container` and attaches it to
``app.state``. FastAPI dependencies resolve it per-request, keeping the
composition root at the application edge and making the wiring testable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, cast

from fastapi import Depends, Request

from app.core.config import Settings, get_settings
from app.core.logging import StructuredLogger, get_logger
from app.projects.git import GitClient
from app.projects.loader import ProjectLoader
from app.projects.manager import RepositoryManager


class Container:
    """Application-wide service registry."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._repository_manager: RepositoryManager | None = None

    @property
    def settings(self) -> Settings:
        """Return the application settings."""
        return self._settings

    @property
    def logger(self) -> StructuredLogger:
        """Return the application logger."""
        return get_logger("xdebug")

    @property
    def repository_manager(self) -> RepositoryManager:
        """Return the lazily constructed repository manager."""
        if self._repository_manager is None:
            workspace = Path(self._settings.workspace_dir).resolve()
            workspace.mkdir(parents=True, exist_ok=True)
            git_client = GitClient(timeout_seconds=self._settings.github_clone_timeout_seconds)
            loader = ProjectLoader(
                max_size_bytes=self._settings.max_repository_size_mb * 1024 * 1024
            )
            self._repository_manager = RepositoryManager(
                workspace_dir=workspace,
                max_repository_size_bytes=self._settings.max_repository_size_mb * 1024 * 1024,
                git_client=git_client,
                loader=loader,
            )
        return self._repository_manager


def get_container(request: Request) -> Container:
    """Resolve the container bound to the current application."""
    return cast(Container, request.app.state.container)


def _settings_from_container(container: Annotated[Container, Depends(get_container)]) -> Settings:
    return container.settings


ContainerDep = Annotated[Container, Depends(get_container)]
SettingsDep = Annotated[Settings, Depends(_settings_from_container)]
