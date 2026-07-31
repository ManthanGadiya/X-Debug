"""Dependency injection.

The application factory builds a :class:`Container` and attaches it to
``app.state``. FastAPI dependencies resolve it per-request, keeping the
composition root at the application edge and making the wiring testable.
"""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import Depends, Request

from app.core.config import Settings, get_settings
from app.core.logging import StructuredLogger, get_logger


class Container:
    """Application-wide service registry."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    @property
    def settings(self) -> Settings:
        """Return the application settings."""
        return self._settings

    @property
    def logger(self) -> StructuredLogger:
        """Return the application logger."""
        return get_logger("xdebug")


def get_container(request: Request) -> Container:
    """Resolve the container bound to the current application."""
    return cast(Container, request.app.state.container)


def _settings_from_container(container: Annotated[Container, Depends(get_container)]) -> Settings:
    return container.settings


ContainerDep = Annotated[Container, Depends(get_container)]
SettingsDep = Annotated[Settings, Depends(_settings_from_container)]
