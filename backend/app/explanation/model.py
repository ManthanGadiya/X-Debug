"""Data model for the explanation engine.

The explanation engine converts a :class:`LocalizationResult` plus its
supporting graph and runtime into a structured, deterministic report. Every
section is derived from analysis artifacts — no model is involved
(docs/XAI_METHEDOLOGY.md §5, §15). The report answers the four questions:

* What happened?  -> :attr:`ExplanationReport.error_summary`
* Where?          -> :attr:`ExplanationReport.where`
* Why?            -> :attr:`ExplanationReport.why`
* How to fix?     -> :attr:`ExplanationReport.suggested_fix`

Each claim stays traceable: evidence references name the artifact that
produced them, and the propagation path mirrors the recorded execution order.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class ExplanationStatus(StrEnum):
    """Lifecycle states of an explanation report."""

    READY = "ready"
    FAILED = "failed"


@dataclass(frozen=True)
class EvidenceReference:
    """One piece of evidence, linked to the analysis artifact that produced it."""

    source: str
    description: str
    score: float
    artifact: str

    def __post_init__(self) -> None:
        """Reject evidence scores outside the [0, 1] range."""
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"Evidence score must be in [0, 1], got {self.score!r}")


@dataclass(frozen=True)
class WhereReference:
    """A concrete code location involved in the failure."""

    file: str
    function: str = ""
    cls: str = ""
    line: int | None = None


@dataclass(frozen=True)
class ExplanationReport:
    """A complete, evidence-backed explanation for one localization result."""

    project_id: str
    status: ExplanationStatus
    created_at: datetime
    updated_at: datetime
    resolved: bool
    error_summary: str
    root_cause: str | None
    why: str
    where: Sequence[WhereReference] = field(default_factory=list)
    evidence: Sequence[EvidenceReference] = field(default_factory=list)
    suggested_fix: str | None = None
    confidence: float = 0.0
    propagation_path: Sequence[str] = field(default_factory=list)
    missing_sources: Sequence[str] = field(default_factory=list)
    insufficient_evidence: bool = False
    error: str | None = None

    def __post_init__(self) -> None:
        """Reject confidence scores outside the [0, 1] range."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be in [0, 1], got {self.confidence!r}")
