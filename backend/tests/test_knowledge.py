"""Unit tests for the knowledge graph builder and manager."""

from __future__ import annotations

import pytest
from app.analysis.callgraph import CallGraphBuilder
from app.analysis.cfg import CFGBuilder
from app.analysis.dataflow import DataFlowAnalyzer
from app.analysis.dependency import DependencyGraphBuilder
from app.analysis.knowledge import KnowledgeGraphBuilder, KnowledgeNodeKind
from app.analysis.knowledge_manager import KnowledgeBuildStatus, KnowledgeGraphManager
from app.analysis.manager import AnalysisManager
from app.analysis.parsers import default_registry
from app.analysis.service import AnalysisResult
from app.core.errors import AnalysisError, NotFoundError, ValidationError
from app.projects.languages import Language
from app.runtime.manager import RuntimeManager, RuntimeStatus
from app.runtime.model import RuntimeException, RuntimeResult, TraceEvent, TraceEventType
from app.runtime.service import RuntimeAnalysis

_UTILS_SOURCE = """class HelperBase:
    def helper(self, x):
        return x * 2
"""

_MAIN_SOURCE = """import math
from utils import HelperBase

class Greeter(HelperBase):
    name = "world"

    def greet(self, who):
        message = f"Hello {who}"
        return message

    def run(self):
        target = self.name
        return self.greet(target)

def main():
    greeter = Greeter()
    if greeter.run():
        return greeter.greet("all")
    return "done"
"""


def _modules() -> tuple[list, dict[str, str]]:
    parser = default_registry().get(Language.PYTHON)
    assert parser is not None
    modules = [
        parser.parse(_UTILS_SOURCE, "utils.py"),
        parser.parse(_MAIN_SOURCE, "main.py"),
    ]
    return modules, {"utils.py": _UTILS_SOURCE, "main.py": _MAIN_SOURCE}


def _analysis() -> AnalysisResult:
    modules, sources = _modules()
    return AnalysisResult(
        project_id="proj-1",
        modules=modules,
        dependency_graph=DependencyGraphBuilder().build(modules),
        call_graph=CallGraphBuilder().build(modules),
        cfg=CFGBuilder().build(modules, sources),
        dataflow_graph=DataFlowAnalyzer().build(modules, sources),
    )


def _runtime() -> RuntimeAnalysis:
    events = [
        TraceEvent(TraceEventType.CALL, "main", "main.py", 17, 0.0, 0),
        TraceEvent(TraceEventType.CALL, "run", "main.py", 11, 1.0, 1),
        TraceEvent(TraceEventType.CALL, "greet", "main.py", 6, 2.0, 2),
        TraceEvent(TraceEventType.RETURN, "greet", "main.py", 8, 3.0, 1),
        TraceEvent(TraceEventType.RETURN, "run", "main.py", 13, 4.0, 0),
        TraceEvent(TraceEventType.RETURN, "main", "main.py", 20, 5.0, 0),
    ]
    return RuntimeAnalysis(
        project_id="proj-1",
        results={"Python": RuntimeResult(status=RuntimeStatus.READY, events=events)},
    )


def test_build_merges_all_sources() -> None:
    """A full analysis plus runtime evidence contributes every source."""
    graph = KnowledgeGraphBuilder().build("proj-1", _analysis(), _runtime())

    assert graph.sources == ["ast", "callgraph", "cfg", "dataflow", "dependency", "runtime"]
    assert graph.missing_sources == []
    assert graph.node_count > 0
    assert graph.edge_count > 0


def test_build_static_only_reports_runtime_missing() -> None:
    """Without runtime evidence the runtime source is reported missing."""
    graph = KnowledgeGraphBuilder().build("proj-1", _analysis(), None)

    assert graph.sources == ["ast", "callgraph", "cfg", "dataflow", "dependency"]
    assert graph.missing_sources == ["runtime"]
    assert "executes_after" not in graph.edge_kinds()


def test_build_runtime_only_reports_static_missing() -> None:
    """Without static analysis only runtime nodes and edges are present."""
    graph = KnowledgeGraphBuilder().build("proj-1", None, _runtime())

    assert graph.sources == ["runtime"]
    assert graph.missing_sources == ["ast", "callgraph", "cfg", "dataflow", "dependency"]
    assert "runtime::Python::main.py::main" in graph.graph.nodes


def test_build_adds_structural_nodes() -> None:
    """The AST contributes project, module, class, function and method nodes."""
    graph = KnowledgeGraphBuilder().build("proj-1", _analysis(), _runtime())
    nodes = graph.graph.nodes
    kinds = {node.kind for node in nodes.values()}

    assert KnowledgeNodeKind.PROJECT in kinds
    assert KnowledgeNodeKind.MODULE in kinds
    assert KnowledgeNodeKind.CLASS in kinds
    assert KnowledgeNodeKind.FUNCTION in kinds
    assert KnowledgeNodeKind.METHOD in kinds
    assert "project::proj-1" in nodes
    assert "main.py" in nodes
    assert "main.py::Greeter" in nodes
    assert "main.py::Greeter.greet" in nodes


def test_build_adds_defines_and_inherits_edges() -> None:
    """Structural containment and inheritance edges are merged."""
    graph = KnowledgeGraphBuilder().build("proj-1", _analysis(), _runtime())
    edges = {(edge.source, edge.target, edge.kind) for edge in graph.graph.edges}

    assert ("project::proj-1", "main.py", "defines") in edges
    assert ("main.py", "main.py::Greeter", "defines") in edges
    assert ("main.py::Greeter", "main.py::Greeter.greet", "defines") in edges
    assert ("main.py::Greeter", "utils.py::HelperBase", "inherits") in edges


def test_build_merges_calls_and_imports() -> None:
    """Dependency and call graph edges survive the merge."""
    graph = KnowledgeGraphBuilder().build("proj-1", _analysis(), _runtime())
    edges = {(edge.source, edge.target, edge.kind) for edge in graph.graph.edges}

    assert ("main.py", "utils.py", "imports") in edges
    assert ("main.py::Greeter.run", "main.py::Greeter.greet", "calls") in edges
    assert ("main.py::main", "external::greeter.run", "calls") in edges
    assert graph.graph.nodes["external::greeter.run"].kind == KnowledgeNodeKind.EXTERNAL


def test_build_maps_cfg_blocks_to_semantic_kinds() -> None:
    """CFG condition blocks map to the condition node kind."""
    graph = KnowledgeGraphBuilder().build("proj-1", _analysis(), None)
    kinds = {node.kind for node in graph.graph.nodes.values()}

    assert KnowledgeNodeKind.CONDITION in kinds
    assert KnowledgeNodeKind.RETURN in kinds
    assert graph.edge_kinds().get("flows_to", 0) > 0


def test_build_reconciles_dataflow_method_ids() -> None:
    """Dataflow nodes for methods are reconciled to their qualified ids."""
    graph = KnowledgeGraphBuilder().build("proj-1", _analysis(), None)
    nodes = graph.graph.nodes

    assert "main.py::Greeter.greet" in nodes
    assert "main.py::greet" not in nodes
    assert "main.py::Greeter.greet::message" in nodes


def test_build_records_execution_evidence() -> None:
    """Runtime calls mark functions as executed and chain ordering edges."""
    graph = KnowledgeGraphBuilder().build("proj-1", _analysis(), _runtime())
    nodes = graph.graph.nodes
    edges = {(edge.source, edge.target, edge.kind) for edge in graph.graph.edges}

    assert nodes["main.py::main"].metadata.get("executed") is True
    assert nodes["main.py::Greeter.run"].metadata.get("executed") is True
    assert ("main.py::main", "main.py::Greeter.run", "executes_after") in edges
    assert ("main.py::Greeter.run", "main.py::Greeter.greet", "executes_after") in edges


def test_build_adds_exception_and_throws_edge() -> None:
    """A captured exception becomes an exception node with a throws edge."""
    events = [
        TraceEvent(TraceEventType.CALL, "main", "main.py", 17, 0.0, 0),
        TraceEvent(TraceEventType.CALL, "run", "main.py", 11, 1.0, 1),
        TraceEvent(TraceEventType.EXCEPTION, "run", "main.py", 12, 2.0, 1, {}, "boom"),
    ]
    result = RuntimeResult(
        status=RuntimeStatus.READY,
        events=events,
        exception=RuntimeException(type="ValueError", message="boom"),
    )
    runtime = RuntimeAnalysis(project_id="proj-1", results={"Python": result})

    graph = KnowledgeGraphBuilder().build("proj-1", _analysis(), runtime)
    nodes = graph.graph.nodes
    edges = {(edge.source, edge.target, edge.kind) for edge in graph.graph.edges}

    assert "exception::Python::ValueError" in nodes
    assert nodes["exception::Python::ValueError"].kind == KnowledgeNodeKind.EXCEPTION
    assert ("main.py::Greeter.run", "exception::Python::ValueError", "throws") in edges


def test_build_runtime_only_creates_runtime_function_nodes() -> None:
    """Runtime functions that cannot link to static nodes are kept as-is."""
    events = [TraceEvent(TraceEventType.CALL, "main", "main.py", 1, 0.0, 0)]
    result = RuntimeResult(status=RuntimeStatus.READY, events=events)
    runtime = RuntimeAnalysis(project_id="proj-1", results={"Python": result})

    graph = KnowledgeGraphBuilder().build("proj-1", None, runtime)
    node = graph.graph.nodes["runtime::Python::main.py::main"]

    assert node.metadata.get("runtime") is True
    assert node.metadata.get("executed") is True


def test_manager_build_ready() -> None:
    """Building stores a ready record retrievable by project id."""
    manager = KnowledgeGraphManager()

    record = manager.build("proj-1", _analysis(), None)

    assert record.status == KnowledgeBuildStatus.READY
    assert record.graph is not None
    assert manager.get("proj-1") is record


def test_manager_build_without_evidence_raises() -> None:
    """Building with neither analysis nor runtime evidence is rejected."""
    manager = KnowledgeGraphManager()

    with pytest.raises(ValidationError):
        manager.build("proj-1", None, None)


def test_manager_get_unknown_project_raises() -> None:
    """Unknown projects return the structured not-found error."""
    manager = KnowledgeGraphManager()

    with pytest.raises(NotFoundError):
        manager.get("missing")


def test_manager_records_failed_build() -> None:
    """A builder failure becomes a failed record instead of an exception."""

    class ExplodingBuilder:
        def build(self, project_id: str, analysis, runtime):
            raise RuntimeError("boom")

    manager = KnowledgeGraphManager(builder=ExplodingBuilder())

    record = manager.build("proj-1", _analysis(), None)

    assert record.status == KnowledgeBuildStatus.FAILED
    assert record.graph is None
    assert "boom" in (record.error or "")


def test_analysis_manager_latest_ready_returns_newest() -> None:
    """latest_ready returns the most recent completed result for a project."""
    manager = AnalysisManager(service=None)  # type: ignore[arg-type]
    first = manager.start("proj-1")
    manager.run(first.id, lambda: AnalysisResult(project_id="proj-1"))
    second = manager.start("proj-1")
    manager.run(second.id, lambda: AnalysisResult(project_id="proj-1"))

    assert manager.latest_ready("proj-1") is second


def test_analysis_manager_latest_ready_ignores_unfinished() -> None:
    """latest_ready skips queued, running and failed records."""
    manager = AnalysisManager(service=None)  # type: ignore[arg-type]
    queued = manager.start("proj-1")
    failed = manager.start("proj-1")

    def _boom() -> AnalysisResult:
        raise AnalysisError(reason="nope", module="test")

    manager.run(failed.id, _boom)

    assert manager.latest_ready("proj-1") is None
    assert manager.latest_ready("other") is None
    assert manager.get(queued.id).status.value == "queued"


def test_runtime_manager_latest_ready_returns_newest() -> None:
    """Runtime latest_ready returns the most recent completed result."""
    manager = RuntimeManager(service=None)  # type: ignore[arg-type]
    first = manager.start("proj-1")
    manager.run(first.id, lambda: RuntimeAnalysis(project_id="proj-1"))
    second = manager.start("proj-1")
    manager.run(second.id, lambda: RuntimeAnalysis(project_id="proj-1"))

    assert manager.latest_ready("proj-1") is second
