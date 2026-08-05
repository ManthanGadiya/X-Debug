"""Unit tests for the static analysis pipeline service."""

from __future__ import annotations

from pathlib import Path

from app.analysis import AnalysisService
from app.analysis.model import ModuleAST
from app.analysis.parsers.base import Parser, ParserRegistry
from app.analysis.parsers.cache import ParseCache
from app.projects.languages import Language
from app.projects.loader import Project, ProjectLoader


class _CountingParser(Parser):
    """Parser stub that records how many times it is invoked."""

    language = Language.PYTHON

    def __init__(self) -> None:
        self.calls = 0

    def parse(self, source: str, path: str) -> ModuleAST:
        self.calls += 1
        return ModuleAST(path=path, language=self.language)


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
    """The analysis reports parsed and failed file counts."""
    _, project = _make_project(tmp_path)
    result = AnalysisService().analyze(project)
    assert result.parsed_file_count == 2
    assert result.failed_file_count == 0
    assert [module.path for module in result.modules] == ["main.py", "utils.py"]


def test_all_graphs_built(tmp_path: Path) -> None:
    """All four static graphs are produced for a project."""
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
    """A cross-module import creates a dependency edge."""
    _, project = _make_project(tmp_path)
    result = AnalysisService().analyze(project)
    assert result.dependency_graph is not None
    kinds = {(e.source, e.target, e.kind) for e in result.dependency_graph.edges}
    assert ("main.py", "utils.py", "imports") in kinds


def test_skips_unsupported_files_and_languages(tmp_path: Path) -> None:
    """Unsupported files are excluded from parsing."""
    _, project = _make_project(tmp_path)
    assert project.source_file_count == 2
    result = AnalysisService().analyze(project)
    assert result.parsed_file_count == 2


def test_partial_failure_records_unparsed(tmp_path: Path) -> None:
    """A file that fails to parse is recorded as unparsed."""
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


def test_c_files_are_parsed_with_python(tmp_path: Path) -> None:
    """C sources are parsed alongside Python in a mixed project."""
    root = tmp_path / "mixed"
    root.mkdir()
    (root / "main.c").write_text(
        '#include "util.h"\nint main(void) { return helper(); }\n', encoding="utf-8"
    )
    (root / "util.h").write_text("int helper(void);\n", encoding="utf-8")
    (root / "app.py").write_text("from util import helper\n", encoding="utf-8")

    loader = ProjectLoader(max_size_bytes=1024 * 1024)
    project = loader.load(root, project_id="proj-3", name="mixed", source="upload")
    result = AnalysisService().analyze(project)

    assert result.parsed_file_count == 3
    assert {module.path for module in result.modules} == {"main.c", "util.h", "app.py"}
    assert result.dependency_graph is not None
    edges = {(e.source, e.target) for e in result.dependency_graph.edges}
    assert ("main.c", "util.h") in edges
    assert result.call_graph is not None
    call_nodes = {node.label for node in result.call_graph.nodes.values()}
    assert "helper" in call_nodes


def test_repeated_analysis_reuses_parsed_modules(tmp_path: Path) -> None:
    """Analyzing the same project twice parses each file only once."""
    _, project = _make_project(tmp_path)
    parser = _CountingParser()
    registry = ParserRegistry(parsers={Language.PYTHON: parser})
    cache = ParseCache(capacity=16)
    service = AnalysisService(parser_registry=registry, cache=cache)

    first = service.analyze(project)
    second = service.analyze(project)

    assert parser.calls == project.source_file_count
    assert first.parsed_file_count == project.source_file_count
    assert second.parsed_file_count == project.source_file_count
    assert cache.hit_count >= project.source_file_count
    assert [module.path for module in second.modules] == [module.path for module in first.modules]


def test_edit_reparses_only_changed_file(tmp_path: Path) -> None:
    """Changing one file between runs reparses exactly that file."""
    loader, project = _make_project(tmp_path)
    parser = _CountingParser()
    registry = ParserRegistry(parsers={Language.PYTHON: parser})
    cache = ParseCache(capacity=16)
    service = AnalysisService(parser_registry=registry, cache=cache)

    service.analyze(project)

    (tmp_path / "repo" / "main.py").write_text("def run():\n    return 42\n", encoding="utf-8")
    updated = loader.load(tmp_path / "repo", project_id="proj-1", name="demo", source="upload")
    service.analyze(updated)

    assert parser.calls == project.source_file_count + 1
