"""Unit tests for the analysis manager lifecycle."""

from __future__ import annotations

from app.analysis import AnalysisManager, AnalysisService
from app.analysis.manager import AnalysisStatus
from app.core.errors import AnalysisError, NotFoundError
from app.projects.loader import Project
from app.projects.manager import RepositoryManager


def _manager() -> AnalysisManager:
    return AnalysisManager(service=AnalysisService())


def _project() -> Project:
    return Project(id="proj-1", name="demo", source="upload", root_path="/tmp/demo")


def test_start_creates_queued_record() -> None:
    record = _manager().start("proj-1")

    assert record.status == AnalysisStatus.QUEUED
    assert record.project_id == "proj-1"
    assert record.result is None


def test_run_transitions_to_ready() -> None:
    manager = _manager()
    record = manager.start("proj-1")
    result = AnalysisService().analyze(_project())

    manager.run(record.id, lambda: result)

    assert manager.get(record.id).status == AnalysisStatus.READY
    assert manager.get(record.id).result is result


def test_run_marks_failed_on_analysis_error() -> None:
    manager = _manager()
    record = manager.start("proj-1")

    def failing() -> None:
        raise AnalysisError(reason="boom", module="Test")

    manager.run(record.id, failing)

    failed = manager.get(record.id)
    assert failed.status == AnalysisStatus.FAILED
    assert failed.error == "boom"
    assert failed.result is None


def test_run_unknown_analysis_raises() -> None:
    manager = _manager()
    try:
        manager.run("missing", lambda: None)
    except NotFoundError as exc:
        assert exc.reason == "Analysis not found"
    else:
        raise AssertionError("expected NotFoundError")


def test_get_unknown_analysis_raises() -> None:
    manager = _manager()
    try:
        manager.get("missing")
    except NotFoundError as exc:
        assert exc.reason == "Analysis not found"
    else:
        raise AssertionError("expected NotFoundError")


def test_get_returns_record() -> None:
    manager = _manager()
    record = manager.start("proj-1")
    assert manager.get(record.id) is record


def test_repository_manager_tracks_projects() -> None:
    from app.projects.git import GitClient

    manager = RepositoryManager(
        workspace_dir=__import__("pathlib").Path("."),
        max_repository_size_bytes=1024,
        git_client=GitClient(timeout_seconds=1),
        loader=None,  # type: ignore[arg-type]
    )
    manager._projects["proj-1"] = _project()

    assert manager.get_project("proj-1") == _project()
    try:
        manager.get_project("missing")
    except NotFoundError as exc:
        assert exc.reason == "Project not found"
    else:
        raise AssertionError("expected NotFoundError")
