"""Data model for the bug localization pipeline.

The pipeline consumes the knowledge graph plus the runtime result and
produces ranked candidates. Each candidate carries one :class:`Evidence`
item per source (docs/BUG_LOCALIZATION.md §22) that supported it, so every
score is explainable. A result is *resolved* only when the top candidate
clears the confidence threshold; otherwise it reports the top hypotheses
and the sources that were missing (docs/BUG_LOCALIZATION.md §25).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import List, Optional, Sequence


class EvidenceSource(StrEnum):
    """Sources that may contribute evidence for a localization candidate."""

    AST = "ast"
    DEPENDENCY_GRAPH = "dependency_graph"
    CALL_GRAPH = "call_graph"
    CFG = "cfg"
    DATA_FLOW = "data_flow"
    RUNTIME_TRACE = "runtime_trace"
    STACK_TRACE = "stack_trace"


@dataclass(frozen=True)
class Evidence:
    """One scored piece of evidence for a candidate, from a single source."""

    source: EvidenceSource
    description: str
    score: float

    def __post_init__(self) -> None:
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"Evidence score must be in [0, 1], got {self.score!r}")


@dataclass(frozen=True)
class LocalizationCandidate:
    """A ranked candidate root cause with its supporting evidence."""

    node_id: str
    label: str
    kind: str
    score: float
    evidence: Sequence[Evidence] = field(default_factory=list)
    reason: str = ""

    def __post_init__(self) -> None:
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"Candidate score must be in [0, 1], got {self.score!r}")


@dataclass(frozen=True)
class LocalizationResult:
    """The outcome of a localization run for one project."""

    resolved: bool
    confidence: float
    summary: str
    root_cause: Optional[LocalizationCandidate]
    candidates: Sequence[LocalizationCandidate]
    propagation_path: List[str]
    evidence_summary: Sequence[Evidence]
    missing_sources: List[str]
    suggested_fix: Optional[str]

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be in [0, 1], got {self.confidence!r}")
        if self.resolved and self.root_cause is None:
            raise ValueError("A resolved localization must name a root cause.")
