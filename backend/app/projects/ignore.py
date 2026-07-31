"""Ignore rules for repository ingestion.

The loader must not ingest binaries, build artifacts, dependency folders, or
media assets. Rules are expressed as a fixed default set plus any
``.gitignore`` patterns found in the repository, matched with pathspec so the
semantics match git (``**``, trailing ``/`` for directories, ``!`` negation).
"""

from __future__ import annotations

from pathlib import Path

import pathspec
from pathspec.gitignore import GitIgnoreSpec

#: Extensions that are never source code.
_BINARY_EXTENSIONS = {
    ".exe",
    ".dll",
    ".so",
    ".dylib",
    ".a",
    ".lib",
    ".o",
    ".obj",
    ".class",
    ".jar",
    ".bin",
    ".dat",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".pyc",
    ".pyo",
    ".whl",
    ".zip",
    ".tar",
    ".gz",
    ".xz",
    ".bz2",
    ".7z",
    ".rar",
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".ico",
    ".bmp",
    ".tiff",
    ".webp",
    ".mp3",
    ".mp4",
    ".wav",
    ".ogg",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
}

#: Directory names that are never source code.
_IGNORED_DIRECTORIES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    "node_modules",
    "bower_components",
    "dist",
    "build",
    ".next",
    ".nuxt",
    ".output",
    "target",
    "out",
    "bin",
    "obj",
    ".idea",
    ".vscode",
    ".gradle",
}

#: File names that are never source code.
_IGNORED_FILES = {".DS_Store", "Thumbs.db"}


class IgnoreRules:
    """Decide whether a repository path should be excluded from ingestion."""

    def __init__(self, gitignore_spec: pathspec.PathSpec | None = None) -> None:
        self._gitignore_spec = gitignore_spec or GitIgnoreSpec.from_lines([])

    @classmethod
    def from_root(cls, root: Path) -> IgnoreRules:
        """Build rules from ``root``, loading any ``.gitignore`` files."""
        return cls(_load_gitignore(root))

    @classmethod
    def from_lines(cls, lines: list[str]) -> IgnoreRules:
        """Build rules from explicit gitignore-style ``lines``."""
        return cls(GitIgnoreSpec.from_lines(lines))

    def is_ignored(self, relative_path: str) -> bool:
        """Return ``True`` when ``relative_path`` must be excluded."""
        parts = relative_path.replace("\\", "/").split("/")
        name = parts[-1]

        return (
            name in _IGNORED_FILES
            or any(part in _IGNORED_DIRECTORIES for part in parts[:-1])
            or _extension_ignored(name)
            or self._gitignore_spec.match_file(relative_path)
        )

    def iter_files(self, root: Path) -> list[Path]:
        """Return the ordered list of files under ``root`` that pass the rules."""
        collected: list[Path] = []
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            if not self.is_ignored(relative):
                collected.append(path)
        return sorted(collected)


def _extension_ignored(name: str) -> bool:
    lower = name.lower()
    return any(lower.endswith(suffix) for suffix in _BINARY_EXTENSIONS)


def _load_gitignore(root: Path) -> pathspec.PathSpec:
    patterns: list[str] = []
    for gitignore_path in root.rglob(".gitignore"):
        try:
            for line in gitignore_path.read_text(encoding="utf-8", errors="replace").splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                patterns.append(stripped)
        except OSError:
            continue
    return GitIgnoreSpec.from_lines(patterns)
