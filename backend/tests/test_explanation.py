"""Unit tests for the explanation engine.

The generator converts a localization result plus the artifacts that produced
it into a structured, evidence-backed report (docs/XAI_METHEDOLOGY.md, Phase 7
of the roadmap). These tests reuse the synthetic graph and runtime builders
from the localization suite so every assertion is hand-checkable.
"""

from __future__ import annotations

import pytest
from app.analysis.graph import Graph, GraphNode
from app.core.errors import NotFoundError
from app.explanation.generator import ExplanationGenerator
from app.explanation.manager import ExplanationManager
from app.explanation.model import EvidenceReference, WhereReference
from app.localization.engine import LocalizationEngine
from app.localization.model import LocalizationResult
from app.runtime.model import RuntimeException, RuntimeResult, TraceEvent, TraceEventType


def _build_graph() -> Graph:
    """Return a synthetic 3-module project with an ``x`` data flow."""
    graph = Graph(name="demo")
    graph.add_node(GraphNode("main.py", "module", "main.py", {"file": "main.py"}))
    graph.add_node(GraphNode("worker.py", "module", "worker.py", {"file": "worker.py"}))
    graph.add_node(GraphNode("compute.py", "module", "compute.py", {"file": "compute.py"}))
    graph.add_node(GraphNode("main.py::main", "function", "main", {"file": "main.py", "line": 1}))
    graph.add_node(
        GraphNode("worker.py::worker", "function", "worker", {"file": "worker.py", "line": 1})
    )
    graph.add_node(
        GraphNode("compute.py::compute", "function", "compute", {"file": "compute.py", "line": 1})
    )
    graph.add_node(GraphNode("compute.py::compute::x", "variable", "x"))
    graph.add_edge("main.py", "worker.py", "imports")
    graph.add_edge("worker.py", "compute.py", "imports")
    graph.add_edge("main.py", "main.py::main", "defines")
    graph.add_edge("worker.py", "worker.py::worker", "defines")
    graph.add_edge("compute.py", "compute.py::compute", "defines")
    graph.add_edge("main.py::main", "worker.py::worker", "calls")
    graph.add_edge("worker.py::worker", "compute.py::compute", "calls")
    graph.add_edge("compute.py::compute", "compute.py::compute::x", "reads")
    graph.add_edge("worker.py::worker", "compute.py::compute::x", "writes")
    return graph


def _build_runtime() -> RuntimeResult:
    """Return a runtime result whose crash occurs inside ``compute``."""
    traceback = (
        "Traceback (most recent call last):\n"
        '  File "main.py", line 2, in <module>\n'
        "    main()\n"
        '  File "main.py", line 5, in main\n'
        "    worker()\n"
        '  File "worker.py", line 7, in worker\n'
        "    return compute(x)\n"
        '  File "compute.py", line 13, in compute\n'
        "    return 10 / x\n"
        "ZeroDivisionError: division by zero\n"
    )
    return RuntimeResult(
        status="failed",
        exit_code=1,
        stdout="",
        stderr=traceback,
        duration_seconds=0.1,
        exception=RuntimeException("ZeroDivisionError", "division by zero"),
        events=[
            TraceEvent(TraceEventType.CALL, "main", "main.py", 5, 0.0, 0, {}),
            TraceEvent(TraceEventType.CALL, "worker", "worker.py", 7, 0.0, 1, {}),
            TraceEvent(TraceEventType.CALL, "compute", "compute.py", 13, 0.0, 2, {}),
            TraceEvent(TraceEventType.EXCEPTION, "compute", "compute.py", 13, 0.0, 3, {"x": 0}),
        ],
        error=None,
    )


def _build_localization() -> LocalizationResult:
    """Return the localization result the engine produces for the fixtures."""
    return LocalizationEngine().localize(_build_graph(), _build_runtime(), language="python")


def test_generate_resolved_report_sections() -> None:
    """A resolved crash yields complete, traceable report sections."""
    report = ExplanationGenerator().generate(
        _build_localization(), graph=_build_graph(), runtime=_build_runtime(), project_id="demo"
    )

    assert report.status.value == "ready"
    assert report.resolved is True
    assert report.project_id == "demo"
    assert report.error_summary == "ZeroDivisionError: division by zero"
    assert report.root_cause is not None
    assert report.root_cause == "worker (worker.py:1)"
    assert report.confidence == 0.713
    assert report.suggested_fix == _build_localization().suggested_fix

    assert "originated in" in report.why
    assert "worker" in report.why
    assert "compute" in report.why
    assert "main" in report.why

    assert report.propagation_path == ["main", "worker", "compute"]

    # Where: deduplicated concrete locations (worker appears as both root cause
    # and a propagation hop).
    assert isinstance(report.where, list)
    assert all(isinstance(ref, WhereReference) for ref in report.where)
    assert len(report.where) >= 3
    workers = [ref for ref in report.where if ref.function == "worker"]
    assert len(workers) == 1

    # Evidence: mapped to human-readable artifact names.
    assert isinstance(report.evidence, list)
    assert all(isinstance(item, EvidenceReference) for item in report.evidence)
    artifacts = {item.artifact for item in report.evidence}
    assert "Runtime Trace" in artifacts
    assert "Stack Trace" in artifacts
    assert "Call Graph" in artifacts
    assert "Data Flow Analysis" in artifacts


def test_generate_uses_runtime_summary_when_exception_absent() -> None:
    """Without a runtime exception the summary text is the "what happened"."""
    localization = _build_localization()
    report = ExplanationGenerator().generate(localization, graph=None, runtime=None)

    assert report.error_summary == localization.summary
    assert report.resolved is True
    assert report.root_cause is not None
    # Missing graph artifacts surface as missing sources rather than crashing.
    assert report.missing_sources == ["cfg"]


def test_generate_below_threshold_is_hypothesis() -> None:
    """Below the confidence threshold the report explains why it is a hypothesis."""
    engine = LocalizationEngine(threshold=0.8)
    localization = engine.localize(_build_graph(), _build_runtime(), language="python")
    report = ExplanationGenerator().generate(
        localization, graph=_build_graph(), runtime=_build_runtime()
    )

    assert report.resolved is False
    assert report.root_cause is None
    assert report.insufficient_evidence is True
    assert "threshold" in report.why
    assert report.suggested_fix is None
    # Evidence is still reported so the reader can judge for themselves.
    assert report.evidence


def test_generate_without_runtime_is_unresolved() -> None:
    """No crash evidence yields an honest, incomplete report."""
    localization = LocalizationEngine().localize(_build_graph(), None, language="python")
    report = ExplanationGenerator().generate(localization, graph=_build_graph(), runtime=None)

    assert report.resolved is False
    assert report.confidence == 0.0
    assert report.root_cause is None
    assert report.insufficient_evidence is True
    assert report.evidence == []
    assert report.why
    assert report.error_summary == localization.summary


def test_generate_without_graph_still_anchors_locations() -> None:
    """Node ids provide file locations even when the graph is absent."""
    report = ExplanationGenerator().generate(_build_localization(), graph=None, runtime=None)

    assert report.resolved is True
    assert report.root_cause == "worker (worker.py::worker)"
    assert report.where
    assert all(ref.file for ref in report.where)


def test_generate_is_deterministic() -> None:
    """Identical inputs produce identical reports."""
    generator = ExplanationGenerator()
    localization = _build_localization()
    graph = _build_graph()
    runtime = _build_runtime()
    first = generator.generate(localization, graph=graph, runtime=runtime)
    second = generator.generate(localization, graph=graph, runtime=runtime)

    assert first.error_summary == second.error_summary
    assert first.why == second.why
    assert first.root_cause == second.root_cause
    assert [ref.line for ref in first.where] == [ref.line for ref in second.where]
    assert [item.score for item in first.evidence] == [item.score for item in second.evidence]


def test_parse_node_id_splits_path_and_qualname() -> None:
    """``path::qualname`` parses into (file, qualname)."""
    generator = ExplanationGenerator()
    assert generator._parse_node_id("compute.py::compute") == ("compute.py", "compute")
    assert generator._parse_node_id("compute.py") == ("compute.py", "")


def test_split_qualname_detects_methods() -> None:
    """``Class.method`` splits into (class, method)."""
    generator = ExplanationGenerator()
    assert generator._split_qualname("Calculator.compute") == ("Calculator", "compute")
    assert generator._split_qualname("compute") == ("", "compute")


class _ExplodingGenerator(ExplanationGenerator):
    """Generator stub that always fails during report construction."""

    def generate(self, *args, **kwargs) -> None:
        raise RuntimeError("boom")


def test_manager_records_generator_failure() -> None:
    """A generator exception is captured as a failed record, not re-raised."""
    manager = ExplanationManager(generator=_ExplodingGenerator())
    record = manager.explain("boom", _build_localization())

    assert record.status.value == "failed"
    assert record.error == "boom"
    assert record.report is None


def test_manager_stores_and_returns_record() -> None:
    """Explain then retrieve by project id."""
    manager = ExplanationManager()
    record = manager.explain("demo", _build_localization())

    assert record.status.value == "ready"
    assert record.report is not None
    assert record.report.resolved is True

    fetched = manager.get("demo")
    assert fetched is record


def test_manager_get_unknown_project_raises() -> None:
    """Fetching an unknown project surfaces a structured error."""
    manager = ExplanationManager()
    with pytest.raises(NotFoundError):
        manager.get("missing")
