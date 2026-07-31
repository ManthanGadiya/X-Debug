"""Unit tests for the static analysis pipeline service."""

from __future__ import annotations

from pathlib import Path

from app.analysis import AnalysisService
from app.projects.loader import Project, ProjectLoader


def _make_project(tmp_path: Path) -> tuple[ProjectLoader, Project]:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "utils.py").write_text("def helper(x):\n    return x * 2\n", encoding="utf-8")
    (root / "main.py").write_text(
        "from utils import helper\n\n"
        "def run():\n"
        "    value = 1\n"
        "    while value < 5:\n"
        "        value = helper(value)\n"
        "    if value > 10:\n"
        "        return value\n"
        "    else:\n"
        "        return 0\n"
        "    return -1\n",
        encoding="utf-8",
    )
    (root / "notes.txt").write_text("not source", encoding="utf-8")

    loader = ProjectLoader(max_size_bytes=1024 * 1024)
    project = loader.load(root, project_id="proj-1", name="demo", source="upload")
    return loader, project


def test_analysis_result_counts(tmp_path: Path) -> None:
    _, project = _make_project(tmp_path)
    result = AnalysisService().analyze(project)
    assert result.parsed_file_count == 2
    assert result.failed_file_count == 0
    assert [module.path for module in result.modules] == ["main.py", "utils.py"]


def test_all_graphs_built(tmp_path: Path) -> None:
    _, project = _make_project(tmp_path)
    result = AnalysisService().analyze(project)
    assert result.dependency_graph is not None
    assert result.call_graph is not None
    assert result.cfg is not None
    assert result.dataflow_graph is not None
    assert result.dependency_graph.node_count > 0
    assert result.call_graph.node_count > 0
    assert result.cfg.node_count > 0
    assert result.dataflow_graph.node_count > 0


def test_dependency_edge_across_modules(tmp_path: Path) -> None:
    _, project = _make_project(tmp_path)
    result = AnalysisService().analyze(project)
    assert result.dependency_graph is not None
    kinds = {(e.source, e.target, e.kind) for e in result.dependency_graph.edges}
    assert ("main.py", "utils.py", "imports") in kinds


def test_skips_unsupported_files_and_languages(tmp_path: Path) -> None:
    _, project = _make_project(tmp_path)
    assert project.source_file_count == 2
    result = AnalysisService().analyze(project)
    assert result.parsed_file_count == 2


def test_partial_failure_records_unparsed(tmp_path: Path) -> None:
    root = tmp_path / "broken"
    root.mkdir()
    (root / "good.py").write_text("x = 1\n", encoding="utf-8")
    (root / "bad.py").write_text("def broken(:\n", encoding="utf-8")

    loader = ProjectLoader(max_size_bytes=1024 * 1024)
    project = loader.load(root, project_id="proj-2", name="broken", source="upload")
    result = AnalysisService().analyze(project)

    assert result.parsed_file_count == 1
    assert result.failed_file_count == 1
    assert "bad.py" in result.unparsed_files
    assert result.cfg is not None
