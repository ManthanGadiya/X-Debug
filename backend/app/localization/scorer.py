"""Confidence scoring for localization candidates.

Confidence is the weighted sum of per-source evidence scores using the
weights specified in docs/BUG_LOCALIZATION.md §23. That table is the single
source of truth; the ARCHITECTURE.md §14 table is explicitly documented as
an example and must not be edited. The scoring is fully deterministic: no
model, no hidden heuristics, no randomness.
"""

from __future__ import annotations

from typing import Dict, Mapping, Optional, Sequence

from app.localization.model import Evidence, EvidenceSource

# Weights from docs/BUG_LOCALIZATION.md §23 (sums to 1.0).
_DEFAULT_WEIGHTS: Dict[EvidenceSource, float] = {
    EvidenceSource.RUNTIME_TRACE: 0.30,
    EvidenceSource.STACK_TRACE: 0.20,
    EvidenceSource.DATA_FLOW: 0.20,
    EvidenceSource.CFG: 0.15,
    EvidenceSource.CALL_GRAPH: 0.10,
    EvidenceSource.DEPENDENCY_GRAPH: 0.03,
    EvidenceSource.AST: 0.02,
}


class ConfidenceScorer:
    """Deterministic confidence scoring using configurable source weights."""

    def __init__(self, weights: Optional[Mapping[EvidenceSource, float]] = None) -> None:
        self._weights: Dict[EvidenceSource, float] = dict(_DEFAULT_WEIGHTS)
        if weights:
            self._weights.update(weights)
        total = sum(self._weights.values())
        if abs(total - 1.0) > 1e-6:
            raise ValueError(
                f"Evidence source weights must sum to 1.0, got {total:.4f}"
            )

    def confidence(self, evidence: Sequence[Evidence]) -> float:
        """Return the weighted confidence of a candidate's evidence list.

        When multiple evidence items come from the same source, the strongest
        one wins for that source; a source never contributes more than its
        full weight.
        """
        best_by_source: Dict[EvidenceSource, float] = {}
        for ev in evidence:
            previous = best_by_source.get(ev.source)
            if previous is None or ev.score > previous:
                best_by_source[ev.source] = ev.score
        return round(
            sum(
                weight * best_by_source.get(source, 0.0)
                for source, weight in self._weights.items()
            ),
            4,
        )

    def best(self, evidence: Sequence[Evidence]) -> Optional[Evidence]:
        """Return the strongest piece of evidence, or ``None`` if empty."""
        if not evidence:
            return None
        return max(evidence, key=lambda ev: ev.score)
