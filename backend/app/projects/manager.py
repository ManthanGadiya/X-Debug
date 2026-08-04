"""Repository Manager service.

Accepts repositories from multiple sources (GitHub clone, local zip upload),
stages them into an isolated workspace directory, and produces a normalized
:class:`Project` via the :class:`ProjectLoader`. Project identifiers are
generated here so every ingested project is addressable by the API layer.
"""

from __future__ import annotations

import uuid
import zipfile
from io import BytesIO
from pathlib import Path

from app.core.errors import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.projects.git import GitClient
from app.projects.loader import Project, ProjectLoader

logger = get_logger(__name__)


class RepositoryManager:
    """Ingest repositories and return normalized project representations."""

    def __init__(
        self,
        workspace_dir: Path,
        max_repository_size_bytes: int,
        git_client: GitClient,
        loader: ProjectLoader,
    ) -> None:
        self._workspace_dir = workspace_dir
        self._max_repository_size_bytes = max_repository_size_bytes
        self._git_client = git_client
        self._loader = loader
        self._projects: dict[str, Project] = {}

    def ingest_upload(self, filename: str, content: bytes) -> Project:
        """Ingest a local repository uploaded as a zip archive."""
        if not filename.lower().endswith(".zip"):
            raise ValidationError(
                reason="Upload must be a zip archive",
                module="Repository Manager",
                detail={"filename": filename},
            )
        if len(content) > self._max_repository_size_bytes:
            raise ValidationError(
                reason="Upload exceeds the maximum allowed size",
                module="Repository Manager",
                detail={
                    "upload_bytes": len(content),
                    "max_bytes": self._max_repository_size_bytes,
                },
            )

        project_id = str(uuid.uuid4())
        staging_dir = self._workspace_dir / project_id / "upload"
        try:
            self._extract_zip(content, staging_dir)
        except zipfile.BadZipFile as exc:
            raise ValidationError(
                reason="Uploaded archive is not a valid zip file",
                module="Repository Manager",
            ) from exc

        root = _detect_single_root(staging_dir)
        name = _archive_name(filename)
        project = self._loader.load(
            root,
            project_id=project_id,
            name=name,
            source="upload",
        )
        self._projects[project.id] = project
        return project

    def ingest_github(self, url: str) -> Project:
        """Clone ``url`` and ingest the resulting repository."""
        project_id = str(uuid.uuid4())
        clone_dir = self._workspace_dir / project_id / "clone"
        clone_dir.parent.mkdir(parents=True, exist_ok=True)

        self._git_client.clone(url, clone_dir)

        root = _detect_single_root(clone_dir)
        name = _github_repo_name(url)
        project = self._loader.load(
            root,
            project_id=project_id,
            name=name,
            source="github",
        )
        self._projects[project.id] = project
        return project

    def get_project(self, project_id: str) -> Project:
        """Return the previously ingested project or raise if unknown."""
        try:
            return self._projects[project_id]
        except KeyError:
            raise NotFoundError(
                reason="Project not found",
                module="Repository Manager",
                detail={"project_id": project_id},
            ) from None

    def list_projects(self) -> list[Project]:
        """Return all ingested projects, most recently created first."""
        projects = list(self._projects.values())
        return [
            project
            for _, project in sorted(
                enumerate(projects),
                key=lambda item: (item[1].created_at, item[0]),
                reverse=True,
            )
        ]

    def _extract_zip(self, content: bytes, destination: Path) -> None:
        destination.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(BytesIO(content)) as archive:
            if _zip_path_traversal(archive):
                raise ValidationError(
                    reason="Uploaded archive contains unsafe paths",
                    module="Repository Manager",
                )
            archive.extractall(destination)


def _detect_single_root(directory: Path) -> Path:
    """Collapse a wrapper directory left by ``.zip`` archives and clones."""
    entries = list(directory.iterdir())
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return directory


def _archive_name(filename: str) -> str:
    return Path(filename).stem


def _github_repo_name(url: str) -> str:
    return url.rstrip("/").split("/")[-1] or "repository"


def _zip_path_traversal(archive: zipfile.ZipFile) -> bool:
    return any(
        ".." in member.filename.split("/") for member in archive.infolist() if not member.is_dir()
    )
