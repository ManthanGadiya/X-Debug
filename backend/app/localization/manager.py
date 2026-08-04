"""Localization Manager service.

Runs the :class:`LocalizationEngine` against a project's knowledge graph and
keeps the latest result per project in memory. Localization is synchronous
and pure::

    graph + runtime -> ready | failed

Localizing without any evidence (an empty or missing knowledge graph) is
rejected: no evidence means no localization. Persistence arrives with the
storage phase.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from app.analysis.graph import Graph
from app.core.errors import NotFoundError, ValidationError
from app.core.logging import StructuredLogger, get_logger
from app.localization.engine import LocalizationEngine
from app.localization.model import LocalizationResult
from app.runtime.model import RuntimeResult

logger = get_logger(__name__)


class LocalizationStatus(StrEnum):
    """Lifecycle states of a localization run."""

    READY = "ready"
    FAILED = "failed"


@dataclass
class LocalizationRecord:
    """The latest localization result for one project."""

    project_id: str
    status: LocalizationStatus
    created_at: datetime
    updated_at: datetime
    result: LocalizationResult | None = None
    error: str | None = None


class LocalizationManager:
    """Track and run localization per project."""

    def __init__(
        self,
        engine: LocalizationEngine | None = None,
        *,
        logger: StructuredLogger = logger,
    ) -> None:
        self._engine = engine or LocalizationEngine()
        self._logger = logger
        self._records: dict[str, LocalizationRecord] = {}
        self._lock = threading.Lock()

    def localize(
        self,
        project_id: str,
        graph: Graph | None,
        runtime: RuntimeResult | None,
        language: str = "python",
        threshold: float | None = None,
    ) -> LocalizationRecord:
        """Localize the crash described by ``runtime`` against ``graph``."""
        if graph is None or graph.node_count == 0:
            raise ValidationError(
                reason="No evidence means no localization",
                module="Localization Manager",
                detail={"project_id": project_id},
            )
        now = datetime.now(UTC)
        try:
            result = self._engine.localize(
                graph, runtime, language=language, threshold=threshold
            )
        except Exception as exc:  # pragma: no cover - defensive finalizer
            record = LocalizationRecord(
                project_id=project_id,
                status=LocalizationStatus.FAILED,
                created_at=now,
                updated_at=datetime.now(UTC),
                error=str(exc),
            )
            with self._lock:
                self._records[project_id] = record
            self._logger.structured(
                logging.ERROR,
                "localization failed",
                project_id=project_id,
                error=str(exc),
            )
            return record

        record = LocalizationRecord(
            project_id=project_id,
            status=LocalizationStatus.READY,
            created_at=now,
            updated_at=datetime.now(UTC),
            result=result,
        )
        with self._lock:
            self._records[project_id] = record
        self._logger.structured(
            logging.INFO,
            "localization complete",
            project_id=project_id,
            resolved=result.resolved,
            confidence=result.confidence,
            candidates=len(result.candidates),
        )
        return record

    def get(self, project_id: str) -> LocalizationRecord:
        """Return the record for ``project_id`` or raise if unknown."""
        with self._lock:
            record = self._records.get(project_id)
        if record is None:
            raise NotFoundError(
                reason="Localization result not found",
                module="Localization Manager",
                detail={"project_id": project_id},
            )
        return record
