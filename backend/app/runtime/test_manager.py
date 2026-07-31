"""Test Manager service.

Holds the records for every test execution run in the current process and
drives the :class:`TestRunner`. Runs follow the documented lifecycle::

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
from app.runtime.model import RuntimeStatus, TestExecution
from app.runtime.test_runner import TestRunner

logger = get_logger(__name__)


@dataclass
class TestRun:
    """One test execution run and its current state."""

    id: str
    project_id: str
    status: RuntimeStatus
    created_at: datetime
    updated_at: datetime
    result: TestExecution | None = None
    error: str | None = None


class TestManager:
    """Track and execute test runs."""

    def __init__(self, service: TestRunner, *, logger: StructuredLogger = logger) -> None:
        self._service = service
        self._logger = logger
        self._records: dict[str, TestRun] = {}
        self._lock = threading.Lock()

    def start(self, project_id: str) -> TestRun:
        """Create a queued test record for ``project_id``."""
        now = datetime.now(UTC)
        record = TestRun(
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
            "test run queued",
            run_id=record.id,
            project_id=project_id,
        )
        return record

    def run(self, run_id: str, execute: Callable[[], TestExecution]) -> None:
        """Execute the test run in the background and finalize the record."""
        record = self._get_or_raise(run_id)
        self._set_status(record, RuntimeStatus.RUNNING)
        try:
            result = execute()
        except Exception as exc:  # pragma: no cover - defensive finalizer
            self._set_status(record, RuntimeStatus.FAILED, error=str(exc))
            return
        record.result = result
        self._set_status(record, RuntimeStatus.READY)

    def get(self, run_id: str) -> TestRun:
        """Return the record for ``run_id`` or raise if unknown."""
        return self._get_or_raise(run_id)

    def _get_or_raise(self, run_id: str) -> TestRun:
        with self._lock:
            record = self._records.get(run_id)
        if record is None:
            raise NotFoundError(
                reason="Test run not found",
                module="Test Manager",
                detail={"run_id": run_id},
            )
        return record

    def _set_status(
        self, record: TestRun, status: RuntimeStatus, *, error: str | None = None
    ) -> None:
        with self._lock:
            record.status = status
            record.updated_at = datetime.now(UTC)
            record.error = error
        self._logger.structured(
            logging.INFO,
            "test status updated",
            run_id=record.id,
            status=status.value,
            project_id=record.project_id,
        )
