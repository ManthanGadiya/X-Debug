"""Pydantic schemas for repository ingestion and project representation."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.projects.languages import Language


class SourceFile(BaseModel):
    """A single source file inside a loaded project."""

    path: str
    language: Language
    size_bytes: int
    lines: int


class ProjectSummary(BaseModel):
    """Top-level metadata describing a loaded repository."""

    id: str
    name: str
    source: str
    root_path: str
    file_count: int
    source_file_count: int
    total_size_bytes: int
    languages: list[Language] = Field(default_factory=list)
    created_at: datetime


class ProjectDetail(ProjectSummary):
    """A loaded project including its indexed source files."""

    files: list[SourceFile] = Field(default_factory=list)


class GitHubCloneRequest(BaseModel):
    """Request body for cloning a GitHub repository."""

    url: str = Field(min_length=1, max_length=2048)
