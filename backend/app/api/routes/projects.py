"""Repository ingestion endpoints.

POST /projects/upload  — ingest a local repository as a zip archive
POST /projects/github  — clone a GitHub repository and ingest it
"""

from __future__ import annotations

from fastapi import APIRouter, File, Path, UploadFile

from app.container import ContainerDep
from app.projects.loader import Project
from app.schemas import GitHubCloneRequest, ProjectDetail, ProjectSummary
from app.schemas.projects import SourceFile

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get(
    "",
    response_model=list[ProjectSummary],
    summary="List ingested projects",
)
def list_projects(container: ContainerDep) -> list[ProjectSummary]:
    """Return all previously ingested projects, most recent first."""
    return [
        ProjectSummary(
            id=project.id,
            name=project.name,
            source=project.source,
            root_path=project.root_path,
            file_count=len(project.files),
            source_file_count=len(project.source_files),
            total_size_bytes=project.total_size_bytes,
            languages=project.languages,
            created_at=project.created_at,
        )
        for project in container.repository_manager.list_projects()
    ]


@router.get(
    "/{project_id}",
    response_model=ProjectDetail,
    summary="Get a project by ID",
)
def get_project(
    container: ContainerDep,
    project_id: str = Path(..., description="Project identifier"),
) -> ProjectDetail:
    """Return the normalized structure of a single ingested project."""
    project = container.repository_manager.get_project(project_id)
    return _to_detail(project)


@router.post(
    "/upload",
    response_model=ProjectDetail,
    summary="Upload a local repository archive",
)
async def upload_project(
    container: ContainerDep,
    file: UploadFile = File(..., description="Zip archive of a repository"),
) -> ProjectDetail:
    """Ingest a zip archive of a repository and return its normalized structure."""
    content = await file.read()
    project = container.repository_manager.ingest_upload(file.filename or "repo.zip", content)
    return _to_detail(project)


@router.post(
    "/github",
    response_model=ProjectDetail,
    summary="Clone and ingest a GitHub repository",
)
def ingest_github(
    container: ContainerDep,
    request: GitHubCloneRequest,
) -> ProjectDetail:
    """Clone a GitHub repository and return its normalized structure."""
    project = container.repository_manager.ingest_github(request.url)
    return _to_detail(project)


def _to_detail(project: Project) -> ProjectDetail:
    return ProjectDetail(
        id=project.id,
        name=project.name,
        source=project.source,
        root_path=project.root_path,
        file_count=len(project.files),
        source_file_count=len(project.source_files),
        total_size_bytes=project.total_size_bytes,
        languages=project.languages,
        created_at=project.created_at,
        files=[
            SourceFile(
                path=file.path,
                language=file.language,
                size_bytes=file.size_bytes,
                lines=file.lines,
            )
            for file in project.source_files
            if file.language is not None
        ],
    )
