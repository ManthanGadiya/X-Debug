"""Pydantic schemas for the bug localization API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class LocalizationRequest(BaseModel):
    """Request body for running localization on a project.

    The project is identified by the URL path; the body only selects the
    analysis language for resolving runtime function names.
    """

    language: str = Field(default="python", min_length=1)


class EvidenceSchema(BaseModel):
    """One scored piece of evidence for a candidate."""

    source: str
    description: str
    score: float


class LocalizationCandidateSchema(BaseModel):
    """A ranked candidate root cause."""

    node_id: str
    label: str
    kind: str
    score: float
    evidence: list[EvidenceSchema] = Field(default_factory=list)
    reason: str = ""


class LocalizationDetail(BaseModel):
    """The outcome of a localization run for one project."""

    project_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    error: str | None = None
    resolved: bool = False
    confidence: float = 0.0
    summary: str = ""
    root_cause: LocalizationCandidateSchema | None = None
    candidates: list[LocalizationCandidateSchema] = Field(default_factory=list)
    propagation_path: list[str] = Field(default_factory=list)
    evidence_summary: list[EvidenceSchema] = Field(default_factory=list)
    missing_sources: list[str] = Field(default_factory=list)
    suggested_fix: str | None = None
