"""Project loading.

The loader walks a normalized repository directory, applies the ignore rules,
and produces an internal :class:`Project` representation: an indexed collection
of source files plus project metadata. It is intentionally stateless and free
of I/O beyond reading the directory it is given.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from app.core.errors import ValidationError
from app.core.logging import StructuredLogger, get_logger
from app.projects.ignore import IgnoreRules
from app.projects.languages import Language, detect_language

logger = get_logger(__name__)


@dataclass
class SourceFileRecord:
    """Internal record of one ingested source file."""

    path: str
    language: Language | None
    size_bytes: int
    lines: int


@dataclass
class Project:
    """Normalized in-memory representation of a loaded repository."""

    id: str
    name: str
    source: str
    root_path: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    files: list[SourceFileRecord] = field(default_factory=list)

    @property
    def source_files(self) -> list[SourceFileRecord]:
        """Return files that map to a supported language."""
        return [file for file in self.files if file.language is not None]

    @property
    def source_file_count(self) -> int:
        """Return the number of files that map to a supported language."""
        return len(self.source_files)

    @property
    def total_size_bytes(self) -> int:
        """Return the summed size of all ingested files."""
        return sum(file.size_bytes for file in self.files)

    @property
    def languages(self) -> list[Language]:
        """Return the distinct supported languages in canonical (declaration) order."""
        present = {file.language for file in self.source_files if file.language is not None}
        return [language for language in Language if language in present]


class ProjectLoader:
    """Load a repository directory into a normalized :class:`Project`."""

    def __init__(
        self,
        max_size_bytes: int,
        *,
        logger: StructuredLogger = logger,
    ) -> None:
        self._max_size_bytes = max_size_bytes
        self._logger = logger

    def load(
        self,
        root: Path,
        *,
        project_id: str,
        name: str,
        source: str,
    ) -> Project:
        """Index ``root`` and return a normalized project representation."""
        if not root.is_dir():
            raise ValidationError(
                reason="Project directory does not exist",
                module="Project Loader",
                detail={"root": str(root)},
            )

        rules = IgnoreRules.from_root(root)
        files = rules.iter_files(root)

        total_bytes = sum(path.stat().st_size for path in files)
        if total_bytes > self._max_size_bytes:
            raise ValidationError(
                reason="Repository exceeds the maximum allowed size",
                module="Project Loader",
                detail={
                    "total_bytes": total_bytes,
                    "max_bytes": self._max_size_bytes,
                },
            )

        records = [self._record(path, root) for path in files]
        project = Project(
            id=project_id,
            name=name,
            source=source,
            root_path=str(root),
            files=records,
        )

        self._logger.structured(
            logging.INFO,
            "project loaded",
            project_id=project.id,
            name=project.name,
            file_count=len(project.files),
            source_file_count=len(project.source_files),
            total_size_bytes=project.total_size_bytes,
        )
        return project

    def _record(self, path: Path, root: Path) -> SourceFileRecord:
        relative = path.relative_to(root).as_posix()
        language = detect_language(relative)
        return SourceFileRecord(
            path=relative,
            language=language,
            size_bytes=path.stat().st_size,
            lines=_count_lines(path),
        )


def _count_lines(path: Path) -> int:
    """Count newlines in a text file; binary or unreadable files return 0."""
    try:
        with path.open("rb") as handle:
            return sum(1 for _ in handle)
    except OSError:
        return 0
