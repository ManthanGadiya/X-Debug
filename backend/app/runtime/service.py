"""Runtime analysis pipeline service.

Orchestrates the Phase 4 runtime stages for a loaded project:

1. Detect the project entry point deterministically per language.
2. Execute it in a bounded child process (timeout + output caps).
3. Capture exceptions, stack traces, variable values, function execution
   order, and execution timestamps into a :class:`RuntimeResult`.

The result is the runtime counterpart of the static :class:`AnalysisResult`.
Partial results are preferred over total failure: a missing entry point or a
compile failure is reported as a structured failure rather than an exception.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from app.core.logging import StructuredLogger, get_logger
from app.projects.languages import Language
from app.projects.loader import Project, SourceFileRecord
from app.runtime.model import RuntimeResult, RuntimeStatus
from app.runtime.runner import RuntimeRunner

logger = get_logger(__name__)

_PYTHON_ENTRY_NAMES = ("__main__.py", "main.py", "app.py", "run.py", "entrypoint.py")


@dataclass
class RuntimeAnalysis:
    """Complete runtime analysis output for one project."""

    project_id: str
    results: dict[str, RuntimeResult] = field(default_factory=dict)

    @property
    def executed_count(self) -> int:
        """Return the number of entry points that executed."""
        return len(self.results)

    @property
    def succeeded(self) -> bool:
        """Return True when at least one entry point ran without raising."""
        return any(result.succeeded for result in self.results.values())


class RuntimeAnalyzer:
    """Execute project entry points and capture runtime behavior."""

    def __init__(
        self,
        runner: RuntimeRunner | None = None,
        *,
        logger: StructuredLogger = logger,
    ) -> None:
        self._runner = runner or RuntimeRunner()
        self._logger = logger

    def analyze(self, project: Project) -> RuntimeAnalysis:
        """Execute every detected entry point of ``project``."""
        root = Path(project.root_path)
        results: dict[str, RuntimeResult] = {}
        for language, entry in _detect_entry_points(project):
            try:
                result = self._runner_for(language)(entry, root)
            except (OSError, ValueError) as exc:
                result = RuntimeResult(
                    status=RuntimeStatus.FAILED,
                    error=f"Execution failed: {exc}",
                )
            results[language.value] = result
            self._logger.structured(
                logging.INFO,
                "runtime execution complete",
                project_id=project.id,
                language=language.value,
                exit_code=result.exit_code,
                events=result.event_count,
                exception=result.exception.type if result.exception else None,
            )
        return RuntimeAnalysis(project_id=project.id, results=results)

    def _runner_for(self, language: Language) -> Callable[[Path, Path], RuntimeResult]:
        if language == Language.PYTHON:
            return self._runner.run_python
        if language == Language.C:
            return self._runner.run_c
        return self._runner.run_cpp


def _detect_entry_points(project: Project) -> list[tuple[Language, Path]]:
    """Return (language, entry_path) pairs in deterministic priority order."""
    root = Path(project.root_path)
    by_language: dict[Language, list[SourceFileRecord]] = {}
    for file in project.source_files:
        if file.language is not None:
            by_language.setdefault(file.language, []).append(file)

    entries: list[tuple[Language, Path]] = []
    for language in Language:
        files = by_language.get(language, [])
        entry = _entry_for(language, files, root)
        if entry is not None:
            entries.append((language, entry))
    return entries


def _entry_for(language: Language, files: list[SourceFileRecord], root: Path) -> Path | None:
    """Detect one entry point per language using deterministic conventions."""
    if language == Language.PYTHON:
        return _python_entry(files, root)
    return _compiled_entry(files, root)


def _python_entry(files: list[SourceFileRecord], root: Path) -> Path | None:
    indexed = {file.path: file for file in files}
    for name in _PYTHON_ENTRY_NAMES:
        record = indexed.get(name)
        if record is not None:
            return root / record.path
    single = files[0] if len(files) == 1 else None
    return root / single.path if single is not None else None


def _compiled_entry(files: list[SourceFileRecord], root: Path) -> Path | None:
    """Prefer a ``main`` file, then any file defining ``main``, else the first."""
    by_name = {file.path.lower(): file for file in files}
    for name in ("main.c", "main.cpp", "main.cc", "main.cxx"):
        record = by_name.get(name)
        if record is not None:
            return root / record.path
    for record in files:
        if _defines_main(root / record.path):
            return root / record.path
    single = files[0] if len(files) == 1 else None
    return root / single.path if single is not None else None


def _defines_main(path: Path) -> bool:
    """Return True when ``path`` contains a top-level ``main`` definition."""
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    for line in content.splitlines():
        stripped = line.strip()
        if "main" in stripped and any(
            token in stripped for token in ("int main", "void main", "auto main", "int32_t main")
        ):
            return True
    return False
