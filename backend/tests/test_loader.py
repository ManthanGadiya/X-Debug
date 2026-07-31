"""Unit tests for the project loader."""

from __future__ import annotations

import logging

import pytest
from app.core.errors import ValidationError
from app.projects.languages import Language
from app.projects.loader import ProjectLoader


@pytest.fixture()
def loader() -> ProjectLoader:
    """Return a loader capped at 1 MiB."""
    return ProjectLoader(max_size_bytes=1024 * 1024)


def test_load_indexes_source_files(tmp_path, loader: ProjectLoader) -> None:
    """A mixed Python/C directory is indexed with correct metadata."""
    (tmp_path / "main.py").write_text("print('hi')\n", encoding="utf-8")
    (tmp_path / "util.c").write_text("int x;\n", encoding="utf-8")

    project = loader.load(tmp_path, project_id="abc", name="demo", source="upload")

    assert project.id == "abc"
    assert project.name == "demo"
    assert project.source == "upload"
    assert len(project.files) == 2
    assert project.source_file_count == 2
    assert project.languages == [Language.PYTHON, Language.C]


def test_load_applies_ignore_rules(tmp_path, loader: ProjectLoader) -> None:
    """Binaries and dependency directories are excluded."""
    (tmp_path / "main.py").write_text("pass\n", encoding="utf-8")
    (tmp_path / "artifact.bin").write_bytes(b"\x00\x01")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "pkg.js").write_text("x", encoding="utf-8")

    project = loader.load(tmp_path, project_id="abc", name="demo", source="upload")

    assert len(project.files) == 1
    assert project.files[0].path == "main.py"


def test_load_ignores_unsupported_languages(tmp_path, loader: ProjectLoader) -> None:
    """Unknown languages are indexed but excluded from source files."""
    (tmp_path / "main.py").write_text("pass\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# docs\n", encoding="utf-8")
    (tmp_path / "data.json").write_text("{}", encoding="utf-8")

    project = loader.load(tmp_path, project_id="abc", name="demo", source="upload")

    assert len(project.files) == 3
    assert len(project.source_files) == 1


def test_load_tracks_lines_and_sizes(tmp_path, loader: ProjectLoader) -> None:
    """Line counts and byte sizes are recorded per file."""
    content = "a\nb\nc\n"
    (tmp_path / "main.py").write_text(content, encoding="utf-8", newline="\n")

    project = loader.load(tmp_path, project_id="abc", name="demo", source="upload")

    (file,) = project.source_files
    assert file.lines == 3
    assert file.size_bytes == len(content)


def test_load_rejects_missing_directory(tmp_path, loader: ProjectLoader) -> None:
    """A missing root raises a validation error."""
    with pytest.raises(ValidationError):
        loader.load(tmp_path / "missing", project_id="abc", name="demo", source="upload")


def test_load_rejects_oversized_repository(tmp_path) -> None:
    """Repositories above the size cap are rejected."""
    small_loader = ProjectLoader(max_size_bytes=10)
    (tmp_path / "main.py").write_text("x" * 100, encoding="utf-8")

    with pytest.raises(ValidationError):
        small_loader.load(tmp_path, project_id="abc", name="demo", source="upload")


def test_loader_uses_structured_logger(tmp_path) -> None:
    """The loader emits a structured log record on completion."""
    seen: list[dict] = []

    class RecordingLogger(logging.Logger):
        def structured(self, level, msg, **fields):  # type: ignore[no-untyped-def]
            seen.append({"msg": msg, "fields": fields})

    recording = RecordingLogger("test")
    loader = ProjectLoader(max_size_bytes=1024, logger=recording)  # type: ignore[arg-type]
    (tmp_path / "main.py").write_text("pass\n", encoding="utf-8")

    loader.load(tmp_path, project_id="abc", name="demo", source="upload")

    assert len(seen) == 1
    assert seen[0]["msg"] == "project loaded"
    assert seen[0]["fields"]["project_id"] == "abc"
