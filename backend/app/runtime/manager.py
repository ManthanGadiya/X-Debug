"""Runtime Manager service.

Holds the runtime records for every execution run in the current process and
drives the :class:`RuntimeAnalyzer`. Runs follow the documented lifecycle::

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

from app.core.errors import NotFoundError
from app.core.logging import StructuredLogger, get_logger
from app.runtime.model import RuntimeStatus
from app.runtime.service import RuntimeAnalysis, RuntimeAnalyzer

logger = get_logger(__name__)


@dataclass
class RuntimeRun:
    """One runtime execution run and its current state."""

    id: str
    project_id: str
    status: RuntimeStatus
    created_at: datetime
    updated_at: datetime
    result: RuntimeAnalysis | None = None
    error: str | None = None


class RuntimeManager:
    """Track and execute runtime analysis runs."""

    def __init__(self, service: RuntimeAnalyzer, *, logger: StructuredLogger = logger) -> None:
        self._service = service
        self._logger = logger
        self._records: dict[str, RuntimeRun] = {}
        self._lock = threading.Lock()

    def start(self, project_id: str) -> RuntimeRun:
        """Create a queued runtime record for ``project_id``."""
        now = datetime.now(UTC)
        record = RuntimeRun(
            id=str(uuid.uuid4()),
            project_id=project_id,
            status=RuntimeStatus.QUEUED,
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._records[record.id] = record
        self._logger.structured(
            logging.INFO,
            "runtime run queued",
            run_id=record.id,
            project_id=project_id,
        )
        return record

    def run(self, run_id: str, execute: Callable[[], RuntimeAnalysis]) -> None:
        """Execute the runtime analysis in the background and finalize the record."""
        record = self._get_or_raise(run_id)
        self._set_status(record, RuntimeStatus.RUNNING)
        try:
            result = execute()
        except Exception as exc:  # pragma: no cover - defensive finalizer
            self._set_status(record, RuntimeStatus.FAILED, error=str(exc))
            return
        record.result = result
        self._set_status(record, RuntimeStatus.READY)

    def get(self, run_id: str) -> RuntimeRun:
        """Return the record for ``run_id`` or raise if unknown."""
        return self._get_or_raise(run_id)

    def list(self) -> list[RuntimeRun]:
        """Return all runtime records, most recently created first."""
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

    def latest_ready(self, project_id: str) -> RuntimeRun | None:
        """Return the most recently completed result for ``project_id``."""
        with self._lock:
            ready = [
                record
                for record in self._records.values()
                if record.project_id == project_id
                and record.status == RuntimeStatus.READY
                and record.result is not None
            ]
        if not ready:
            return None
        return max(reversed(ready), key=lambda record: record.updated_at)

    def _get_or_raise(self, run_id: str) -> RuntimeRun:
        with self._lock:
            record = self._records.get(run_id)
        if record is None:
            raise NotFoundError(
                reason="Runtime run not found",
                module="Runtime Manager",
                detail={"run_id": run_id},
            )
        return record

    def _set_status(
        self, record: RuntimeRun, status: RuntimeStatus, *, error: str | None = None
    ) -> None:
        with self._lock:
            record.status = status
            record.updated_at = datetime.now(UTC)
            record.error = error
        self._logger.structured(
            logging.INFO,
            "runtime status updated",
            run_id=record.id,
            status=status.value,
            project_id=record.project_id,
        )
