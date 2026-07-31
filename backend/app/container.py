"""Dependency injection.

The application factory builds a :class:`Container` and attaches it to
``app.state``. FastAPI dependencies resolve it per-request, keeping the
composition root at the application edge and making the wiring testable.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, cast

from fastapi import Depends, Request

from app.analysis.manager import AnalysisManager
from app.analysis.service import AnalysisService
from app.core.config import Settings, get_settings
from app.core.logging import StructuredLogger, get_logger
from app.projects.git import GitClient
from app.projects.loader import ProjectLoader
from app.projects.manager import RepositoryManager
from app.runtime.manager import RuntimeManager
from app.runtime.runner import RuntimeRunner
from app.runtime.service import RuntimeAnalyzer
from app.runtime.test_manager import TestManager
from app.runtime.test_runner import TestRunner


class Container:
    """Application-wide service registry."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._repository_manager: RepositoryManager | None = None
        self._analysis_service: AnalysisService | None = None
        self._analysis_manager: AnalysisManager | None = None
        self._runtime_analyzer: RuntimeAnalyzer | None = None
        self._runtime_manager: RuntimeManager | None = None
        self._test_runner: TestRunner | None = None
        self._test_manager: TestManager | None = None

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

    @property
    def analysis_service(self) -> AnalysisService:
        """Return the lazily constructed static analysis service."""
        if self._analysis_service is None:
            self._analysis_service = AnalysisService()
        return self._analysis_service

    @property
    def analysis_manager(self) -> AnalysisManager:
        """Return the lazily constructed analysis manager."""
        if self._analysis_manager is None:
            self._analysis_manager = AnalysisManager(service=self.analysis_service)
        return self._analysis_manager

    @property
    def runtime_analyzer(self) -> RuntimeAnalyzer:
        """Return the lazily constructed runtime analyzer."""
        if self._runtime_analyzer is None:
            runner = RuntimeRunner(
                timeout_seconds=self._settings.runtime_timeout_seconds,
                max_output_chars=self._settings.max_output_chars,
                max_trace_events=self._settings.max_trace_events,
            )
            self._runtime_analyzer = RuntimeAnalyzer(runner=runner)
        return self._runtime_analyzer

    @property
    def runtime_manager(self) -> RuntimeManager:
        """Return the lazily constructed runtime manager."""
        if self._runtime_manager is None:
            self._runtime_manager = RuntimeManager(service=self.runtime_analyzer)
        return self._runtime_manager

    @property
    def test_runner(self) -> TestRunner:
        """Return the lazily constructed test runner."""
        if self._test_runner is None:
            self._test_runner = TestRunner(
                timeout_seconds=self._settings.runtime_timeout_seconds * 2,
                max_output_chars=self._settings.max_output_chars,
            )
        return self._test_runner

    @property
    def test_manager(self) -> TestManager:
        """Return the lazily constructed test manager."""
        if self._test_manager is None:
            self._test_manager = TestManager(service=self.test_runner)
        return self._test_manager


def get_container(request: Request) -> Container:
    """Resolve the container bound to the current application."""
    return cast(Container, request.app.state.container)


def _settings_from_container(container: Annotated[Container, Depends(get_container)]) -> Settings:
    return container.settings


ContainerDep = Annotated[Container, Depends(get_container)]
SettingsDep = Annotated[Settings, Depends(_settings_from_container)]
