"""Analysis Manager service.

Holds the analysis records for every analysis run in the current process and
drives the :class:`AnalysisService`. Runs follow the documented lifecycle::

    queued → running → ready

A failure moves the record to ``failed`` with a structured error message.
Results are kept in memory; persistence arrives with the storage phase.
"""

from __future__ import annotations

import logging
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from app.analysis.service import AnalysisResult, AnalysisService
from app.core.errors import AnalysisError, NotFoundError
from app.core.logging import StructuredLogger, get_logger

logger = get_logger(__name__)


class AnalysisStatus(StrEnum):
    """Lifecycle states of an analysis run."""

    QUEUED = "queued"
    RUNNING = "running"
    READY = "ready"
    FAILED = "failed"


@dataclass
class AnalysisRecord:
    """One analysis run and its current state."""

    id: str
    project_id: str
    status: AnalysisStatus
    created_at: datetime
    updated_at: datetime
    result: AnalysisResult | None = None
    error: str | None = None


class AnalysisManager:
    """Track and execute analysis runs."""

    def __init__(self, service: AnalysisService, *, logger: StructuredLogger = logger) -> None:
        self._service = service
        self._logger = logger
        self._records: dict[str, AnalysisRecord] = {}
        self._lock = threading.Lock()

    def start(self, project_id: str) -> AnalysisRecord:
        """Create a queued analysis record for ``project_id``."""
        now = datetime.now(UTC)
        record = AnalysisRecord(
            id=str(uuid.uuid4()),
            project_id=project_id,
            status=AnalysisStatus.QUEUED,
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._records[record.id] = record
        self._logger.structured(
            logging.INFO,
            "analysis queued",
            analysis_id=record.id,
            project_id=project_id,
        )
        return record

    def run(self, analysis_id: str, analyze: Callable[[], AnalysisResult]) -> None:
        """Execute the analysis in the background and finalize the record."""
        record = self._get_or_raise(analysis_id)
        self._set_status(record, AnalysisStatus.RUNNING)
        try:
            result = analyze()
        except AnalysisError as exc:
            self._set_status(record, AnalysisStatus.FAILED, error=str(exc))
            return
        record.result = result
        self._set_status(record, AnalysisStatus.READY)

    def get(self, analysis_id: str) -> AnalysisRecord:
        """Return the record for ``analysis_id`` or raise if unknown."""
        return self._get_or_raise(analysis_id)

    def list(self) -> list[AnalysisRecord]:
        """Return all analysis records, most recently created first."""
        with self._lock:
            records = list(self._records.values())
        return [
            record
            for _, record in sorted(
                enumerate(records),
                key=lambda item: (item[1].created_at, item[0]),
                reverse=True,
            )
        ]

    def latest_ready(self, project_id: str) -> AnalysisRecord | None:
        """Return the most recently completed result for ``project_id``."""
        with self._lock:
            ready = [
                record
                for record in self._records.values()
                if record.project_id == project_id
                and record.status == AnalysisStatus.READY
                and record.result is not None
            ]
        if not ready:
            return None
        return max(reversed(ready), key=lambda record: record.updated_at)

    def _get_or_raise(self, analysis_id: str) -> AnalysisRecord:
        with self._lock:
            record = self._records.get(analysis_id)
        if record is None:
            raise NotFoundError(
                reason="Analysis not found",
                module="Analysis Manager",
                detail={"analysis_id": analysis_id},
            )
        return record

    def _set_status(
        self, record: AnalysisRecord, status: AnalysisStatus, *, error: str | None = None
    ) -> None:
        with self._lock:
            record.status = status
            record.updated_at = datetime.now(UTC)
            record.error = error
        self._logger.structured(
            logging.INFO,
            "analysis status updated",
            analysis_id=record.id,
            status=status.value,
            project_id=record.project_id,
        )
