"""Bug localization engine (Phase 6).

Consumes the knowledge graph produced by the analysis layer and the runtime
result produced by the runtime layer, then produces ranked, explainable
localization candidates without any machine learning. Confidence is a
deterministic weighted sum of per-source evidence scores; see
docs/BUG_LOCALIZATION.md §23.
"""

from app.localization.engine import LocalizationEngine
from app.localization.manager import LocalizationManager
from app.localization.model import (
    Evidence,
    EvidenceSource,
    LocalizationCandidate,
    LocalizationResult,
)
from app.localization.scorer import ConfidenceScorer

__all__ = [
    "Evidence",
    "EvidenceSource",
    "LocalizationCandidate",
    "LocalizationResult",
    "ConfidenceScorer",
    "LocalizationEngine",
    "LocalizationManager",
]
