"""Explanation engine — Phase 7 of the roadmap (docs/XAI_METHEDOLOGY.md).

Converts localization output into understandable, evidence-backed reports.
"""

from app.explanation.generator import ExplanationGenerator
from app.explanation.manager import ExplanationManager
from app.explanation.model import (
    EvidenceReference,
    ExplanationReport,
    ExplanationStatus,
    WhereReference,
)

__all__ = [
    "EvidenceReference",
    "ExplanationGenerator",
    "ExplanationManager",
    "ExplanationReport",
    "ExplanationStatus",
    "WhereReference",
]
