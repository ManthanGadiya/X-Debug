"""Pydantic schemas for the explanation API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class EvidenceReferenceSchema(BaseModel):
    """One piece of evidence, linked to the analysis artifact that produced it."""

    source: str
    description: str
    score: float
    artifact: str


class WhereReferenceSchema(BaseModel):
    """A concrete code location involved in the failure."""

    file: str
    function: str = ""
    cls: str = ""
    line: int | None = None


class ExplanationDetail(BaseModel):
    """A complete, evidence-backed explanation for one localization result."""

    project_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    error: str | None = None
    resolved: bool = False
    error_summary: str = ""
    root_cause: str | None = None
    why: str = ""
    where: list[WhereReferenceSchema] = Field(default_factory=list)
    evidence: list[EvidenceReferenceSchema] = Field(default_factory=list)
    suggested_fix: str | None = None
    confidence: float = 0.0
    propagation_path: list[str] = Field(default_factory=list)
    missing_sources: list[str] = Field(default_factory=list)
    insufficient_evidence: bool = False
