"""Unit tests for the repository manager."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
from app.core.errors import ValidationError
from app.projects.git import GitClient
from app.projects.loader import ProjectLoader
from app.projects.manager import RepositoryManager


@pytest.fixture()
def manager(tmp_path) -> RepositoryManager:
    """Return a repository manager backed by a temp workspace."""
    loader = ProjectLoader(max_size_bytes=1024 * 1024)
    git = GitClient(timeout_seconds=10)
    return RepositoryManager(
        workspace_dir=tmp_path / "workspace",
        max_repository_size_bytes=1024 * 1024,
        git_client=git,
        loader=loader,
    )


def _zip_bytes(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def test_ingest_upload_extracts_and_loads(tmp_path, manager: RepositoryManager) -> None:
    """A zip upload is extracted into the workspace and loaded."""
    payload = _zip_bytes({"main.py": b"print('hi')\n", "README.md": b"docs\n"})

    project = manager.ingest_upload("repo.zip", payload)

    assert project.source == "upload"
    assert project.name == "repo"
    assert len(project.files) == 2
    assert [file.path for file in project.source_files] == ["main.py"]
    assert (tmp_path / "workspace" / project.id / "upload").is_dir()


def test_ingest_upload_collapses_single_wrapper_dir(tmp_path, manager: RepositoryManager) -> None:
    """A single top-level wrapper directory is collapsed."""
    payload = _zip_bytes({"project/main.py": b"pass\n"})

    project = manager.ingest_upload("project.zip", payload)

    assert project.root_path.replace("\\", "/").endswith("upload/project")
    assert [file.path for file in project.source_files] == ["main.py"]


def test_ingest_upload_rejects_non_zip(manager: RepositoryManager) -> None:
    """Non-zip uploads are rejected."""
    with pytest.raises(ValidationError, match="zip"):
        manager.ingest_upload("repo.tar.gz", b"not a zip")


def test_ingest_upload_rejects_invalid_zip(manager: RepositoryManager) -> None:
    """Corrupt archives are rejected."""
    with pytest.raises(ValidationError, match="valid zip"):
        manager.ingest_upload("repo.zip", b"not really a zip")


def test_ingest_upload_rejects_oversized(manager: RepositoryManager) -> None:
    """Oversized uploads are rejected before extraction."""
    with pytest.raises(ValidationError, match="maximum allowed size"):
        manager.ingest_upload("repo.zip", b"x" * (1024 * 1024 + 1))


def test_ingest_upload_rejects_path_traversal(manager: RepositoryManager) -> None:
    """Archives containing path traversal are rejected."""
    payload = _zip_bytes({"../escape.py": b"pass\n"})

    with pytest.raises(ValidationError, match="unsafe paths"):
        manager.ingest_upload("repo.zip", payload)


class FakeGitClient:
    """In-memory stand-in for the system git executable."""

    def __init__(self, contents: dict[str, str]) -> None:
        self.contents = contents
        self.cloned: list[tuple[str, Path]] = []

    def clone(self, url: str, destination: Path) -> None:
        """Write fake repository files into ``destination``."""
        self.cloned.append((url, destination))
        destination.mkdir(parents=True, exist_ok=True)
        for name, content in self.contents.items():
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")


def test_ingest_github_clones_and_loads(tmp_path) -> None:
    """A GitHub clone is staged and normalized."""
    fake_git = FakeGitClient({"main.py": "pass\n", "lib/util.py": "x = 1\n"})
    loader = ProjectLoader(max_size_bytes=1024 * 1024)
    manager = RepositoryManager(
        workspace_dir=tmp_path / "workspace",
        max_repository_size_bytes=1024 * 1024,
        git_client=fake_git,  # type: ignore[arg-type]
        loader=loader,
    )

    project = manager.ingest_github("https://github.com/acme/demo")

    assert project.source == "github"
    assert project.name == "demo"
    assert len(fake_git.cloned) == 1
    assert fake_git.cloned[0][0] == "https://github.com/acme/demo"
    assert len(project.source_files) == 2
