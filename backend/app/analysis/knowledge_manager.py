"""Knowledge Graph Manager service.

Holds the unified knowledge graph for every project in the current process and
drives the :class:`KnowledgeGraphBuilder`. A build is synchronous and pure::

    build -> ready | failed

Building without any evidence (no analysis and no runtime result) is rejected;
a builder failure is recorded as ``failed`` with a structured error message.
Graphs are kept in memory; persistence arrives with the storage phase.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from app.analysis.knowledge import KnowledgeGraph, KnowledgeGraphBuilder
from app.analysis.service import AnalysisResult
from app.core.errors import NotFoundError, ValidationError
from app.core.logging import StructuredLogger, get_logger
from app.runtime.service import RuntimeAnalysis

logger = get_logger(__name__)


class KnowledgeBuildStatus(StrEnum):
    """Lifecycle states of a knowledge graph build."""

    READY = "ready"
    FAILED = "failed"


@dataclass
class KnowledgeRecord:
    """The unified knowledge graph for one project and its build state."""

    project_id: str
    status: KnowledgeBuildStatus
    created_at: datetime
    updated_at: datetime
    graph: KnowledgeGraph | None = None
    error: str | None = None


class KnowledgeGraphManager:
    """Track and build the unified knowledge graph per project."""

    def __init__(
        self,
        builder: KnowledgeGraphBuilder | None = None,
        *,
        logger: StructuredLogger = logger,
    ) -> None:
        self._builder = builder or KnowledgeGraphBuilder()
        self._logger = logger
        self._records: dict[str, KnowledgeRecord] = {}
        self._lock = threading.Lock()

    def build(
        self,
        project_id: str,
        analysis: AnalysisResult | None,
        runtime: RuntimeAnalysis | None,
    ) -> KnowledgeRecord:
        """Merge the latest evidence for ``project_id`` into a knowledge graph."""
        if analysis is None and runtime is None:
            raise ValidationError(
                reason="Cannot build a knowledge graph without evidence",
                module="Knowledge Graph Manager",
                detail={"project_id": project_id},
            )
        now = datetime.now(UTC)
        try:
            graph = self._builder.build(project_id, analysis, runtime)
        except Exception as exc:  # pragma: no cover - defensive finalizer
            record = KnowledgeRecord(
                project_id=project_id,
                status=KnowledgeBuildStatus.FAILED,
                created_at=now,
                updated_at=datetime.now(UTC),
                error=str(exc),
            )
            with self._lock:
                self._records[project_id] = record
            self._logger.structured(
                logging.ERROR,
                "knowledge graph build failed",
                project_id=project_id,
                error=str(exc),
            )
            return record

        record = KnowledgeRecord(
            project_id=project_id,
            status=KnowledgeBuildStatus.READY,
            created_at=now,
            updated_at=datetime.now(UTC),
            graph=graph,
        )
        with self._lock:
            self._records[project_id] = record
        self._logger.structured(
            logging.INFO,
            "knowledge graph ready",
            project_id=project_id,
            nodes=graph.node_count,
            edges=graph.edge_count,
            sources=graph.sources,
        )
        return record

    def get(self, project_id: str) -> KnowledgeRecord:
        """Return the record for ``project_id`` or raise if unknown."""
        with self._lock:
            record = self._records.get(project_id)
        if record is None:
            raise NotFoundError(
                reason="Knowledge graph not found",
                module="Knowledge Graph Manager",
                detail={"project_id": project_id},
            )
        return record
