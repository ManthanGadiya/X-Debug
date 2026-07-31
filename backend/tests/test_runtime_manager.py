"""Tests for the runtime manager."""

from __future__ import annotations

import pytest
from app.core.errors import NotFoundError
from app.runtime.manager import RuntimeManager
from app.runtime.model import RuntimeStatus
from app.runtime.service import RuntimeAnalysis


class _FakeAnalyzer:
    def analyze(self, project: object) -> RuntimeAnalysis:
        return RuntimeAnalysis(project_id=getattr(project, "id", "p1"))


def _result() -> RuntimeAnalysis:
    return RuntimeAnalysis(project_id="p1")


def test_start_creates_queued_record() -> None:
    manager = RuntimeManager(service=_FakeAnalyzer())  # type: ignore[arg-type]
    record = manager.start("p1")
    assert record.id
    assert record.project_id == "p1"
    assert record.status == RuntimeStatus.QUEUED
    assert record.result is None


def test_run_transitions_to_ready() -> None:
    manager = RuntimeManager(service=_FakeAnalyzer())  # type: ignore[arg-type]
    record = manager.start("p1")
    manager.run(record.id, _result)
    assert record.status == RuntimeStatus.READY
    assert record.result is not None
    assert record.result.project_id == "p1"


def test_run_marks_failed_on_error() -> None:
    manager = RuntimeManager(service=_FakeAnalyzer())  # type: ignore[arg-type]

    def explode() -> RuntimeAnalysis:
        raise RuntimeError("boom")

    record = manager.start("p1")
    manager.run(record.id, explode)
    assert record.status == RuntimeStatus.FAILED
    assert record.error == "boom"


def test_get_returns_record() -> None:
    manager = RuntimeManager(service=_FakeAnalyzer())  # type: ignore[arg-type]
    record = manager.start("p1")
    assert manager.get(record.id) is record


def test_get_unknown_raises() -> None:
    manager = RuntimeManager(service=_FakeAnalyzer())  # type: ignore[arg-type]
    with pytest.raises(NotFoundError):
        manager.get("missing")
