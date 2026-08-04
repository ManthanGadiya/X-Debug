"""Explanation Manager service.

Generates :class:`ExplanationReport` objects for a project's latest
localization result and keeps the most recent report per project in memory.
Generation is synchronous and deterministic; persistence arrives with the
storage phase.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import UTC, datetime

from app.analysis.graph import Graph
from app.core.errors import NotFoundError
from app.core.logging import StructuredLogger, get_logger
from app.explanation.generator import ExplanationGenerator
from app.explanation.model import ExplanationReport, ExplanationStatus
from app.localization.model import LocalizationResult
from app.runtime.model import RuntimeResult

logger = get_logger(__name__)


@dataclass
class ExplanationRecord:
    """The latest explanation report for one project."""

    project_id: str
    status: ExplanationStatus
    created_at: datetime
    updated_at: datetime
    report: ExplanationReport | None = None
    error: str | None = None


class ExplanationManager:
    """Track and generate explanations per project."""

    def __init__(
        self,
        generator: ExplanationGenerator | None = None,
        *,
        logger: StructuredLogger = logger,
    ) -> None:
        self._generator = generator or ExplanationGenerator()
        self._logger = logger
        self._records: dict[str, ExplanationRecord] = {}
        self._lock = threading.Lock()

    def explain(
        self,
        project_id: str,
        localization: LocalizationResult,
        graph: Graph | None = None,
        runtime: RuntimeResult | None = None,
    ) -> ExplanationRecord:
        """Generate and store the explanation for ``localization``."""
        now = datetime.now(UTC)
        try:
            report = self._generator.generate(
                localization,
                graph=graph,
                runtime=runtime,
                project_id=project_id,
            )
        except Exception as exc:  # pragma: no cover - defensive finalizer
            record = ExplanationRecord(
                project_id=project_id,
                status=ExplanationStatus.FAILED,
                created_at=now,
                updated_at=datetime.now(UTC),
                error=str(exc),
            )
            with self._lock:
                self._records[project_id] = record
            self._logger.structured(
                logging.ERROR,
                "explanation failed",
                project_id=project_id,
                error=str(exc),
            )
            return record

        record = ExplanationRecord(
            project_id=project_id,
            status=ExplanationStatus.READY,
            created_at=now,
            updated_at=datetime.now(UTC),
            report=report,
        )
        with self._lock:
            self._records[project_id] = record
        self._logger.structured(
            logging.INFO,
            "explanation complete",
            project_id=project_id,
            resolved=report.resolved,
            confidence=report.confidence,
            evidence=len(report.evidence),
        )
        return record

    def get(self, project_id: str) -> ExplanationRecord:
        """Return the record for ``project_id`` or raise if unknown."""
        with self._lock:
            record = self._records.get(project_id)
        if record is None:
            raise NotFoundError(
                reason="Explanation report not found",
                module="Explanation Manager",
                detail={"project_id": project_id},
            )
        return record
