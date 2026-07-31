"""Tests for the test manager."""

from __future__ import annotations

import pytest
from app.core.errors import NotFoundError
from app.runtime.model import RuntimeStatus, TestExecution, TestSuite
from app.runtime.test_manager import TestManager


class _FakeRunner:
    def run(self, project: object) -> TestExecution:
        return TestExecution(project_id=getattr(project, "id", "p1"))


def _result() -> TestExecution:
    suite = TestSuite(
        language="Python",
        tests_run=1,
        passed=1,
        failed=0,
        skipped=0,
        duration_seconds=0.1,
    )
    return TestExecution(project_id="p1", suites={"Python": suite})


def test_start_creates_queued_record() -> None:
    """Starting a test run creates a queued record."""
    manager = TestManager(service=_FakeRunner())  # type: ignore[arg-type]
    record = manager.start("p1")
    assert record.id
    assert record.project_id == "p1"
    assert record.status == RuntimeStatus.QUEUED
    assert record.result is None


def test_run_transitions_to_ready() -> None:
    """A completed test run transitions to ready."""
    manager = TestManager(service=_FakeRunner())  # type: ignore[arg-type]
    record = manager.start("p1")
    manager.run(record.id, _result)
    assert record.status == RuntimeStatus.READY
    assert record.result is not None
    assert record.result.project_id == "p1"
    assert record.result.succeeded


def test_run_marks_failed_on_error() -> None:
    """A failing test run marks the record failed."""
    manager = TestManager(service=_FakeRunner())  # type: ignore[arg-type]

    def explode() -> TestExecution:
        raise RuntimeError("boom")

    record = manager.start("p1")
    manager.run(record.id, explode)
    assert record.status == RuntimeStatus.FAILED
    assert record.error == "boom"


def test_get_returns_record() -> None:
    """Fetching a record returns the stored instance."""
    manager = TestManager(service=_FakeRunner())  # type: ignore[arg-type]
    record = manager.start("p1")
    assert manager.get(record.id) is record


def test_get_unknown_raises() -> None:
    """Fetching an unknown run raises NotFoundError."""
    manager = TestManager(service=_FakeRunner())  # type: ignore[arg-type]
    with pytest.raises(NotFoundError):
        manager.get("missing")
