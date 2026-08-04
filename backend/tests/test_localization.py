"""Unit tests for the bug localization pipeline.

The localization engine reasons deterministically over a knowledge graph plus
a runtime result (docs/BUG_LOCALIZATION.md). These tests use a synthetic graph
so every score is hand-computable from the weights in §23.
"""

from __future__ import annotations

import pytest
from app.analysis.graph import Graph, GraphNode
from app.core.errors import NotFoundError, ValidationError
from app.localization.engine import LocalizationEngine
from app.localization.manager import LocalizationManager
from app.localization.model import (
    Evidence,
    EvidenceSource,
    LocalizationResult,
)
from app.localization.scorer import ConfidenceScorer
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
    events = [
        TraceEvent(TraceEventType.CALL, "main", "main.py", 5, 0.0, 0, {}),
        TraceEvent(TraceEventType.CALL, "worker", "worker.py", 7, 0.0, 1, {}),
        TraceEvent(TraceEventType.CALL, "compute", "compute.py", 13, 0.0, 2, {}),
        TraceEvent(TraceEventType.EXCEPTION, "compute", "compute.py", 13, 0.0, 3, {"x": 0}),
    ]
    return RuntimeResult(
        status="failed",
        exit_code=1,
        stdout="",
        stderr=traceback,
        duration_seconds=0.1,
        exception=RuntimeException("ZeroDivisionError", "division by zero"),
        events=events,
        error=None,
    )


def _build_runtime_win() -> RuntimeResult:
    """Like :func:`_build_runtime` but with Windows absolute file paths.

    The runtime harness reports absolute filesystem paths (backslashes on
    Windows) while the static graph stores project-relative paths, so the
    engine must normalize before matching (regression: forward-slash-only
    suffix matching never resolved on Windows).
    """
    traceback = (
        "Traceback (most recent call last):\n"
        '  File "C:\\repo\\main.py", line 2, in <module>\n'
        "    main()\n"
        '  File "C:\\repo\\main.py", line 5, in main\n'
        "    worker()\n"
        '  File "C:\\repo\\worker.py", line 7, in worker\n'
        "    return compute(x)\n"
        '  File "C:\\repo\\compute.py", line 13, in compute\n'
        "    return 10 / x\n"
        "ZeroDivisionError: division by zero\n"
    )
    events = [
        TraceEvent(TraceEventType.CALL, "main", r"C:\repo\main.py", 5, 0.0, 0, {}),
        TraceEvent(TraceEventType.CALL, "worker", r"C:\repo\worker.py", 7, 0.0, 1, {}),
        TraceEvent(TraceEventType.CALL, "compute", r"C:\repo\compute.py", 13, 0.0, 2, {}),
        TraceEvent(
            TraceEventType.EXCEPTION, "compute", r"C:\repo\compute.py", 13, 0.0, 3, {"x": 0}
        ),
    ]
    return RuntimeResult(
        status="failed",
        exit_code=1,
        stdout="",
        stderr=traceback,
        duration_seconds=0.1,
        exception=RuntimeException("ZeroDivisionError", "division by zero"),
        events=events,
        error=None,
    )


def _build_graph_with_cfg() -> Graph:
    """Like :func:`_build_graph` plus a CFG for ``compute``.

    The knowledge builder canonicalizes the return statement onto a node with
    kind ``"return"`` (app/analysis/knowledge.py ``_block_kind``), so the
    localization extractor must treat it as part of the function's control
    flow (regression: only ``"block"`` nodes were indexed, hiding the crash
    line and degrading CFG evidence to 0.8).
    """
    graph = _build_graph()
    graph.add_node(
        GraphNode(
            "compute.py::compute:start", "block", "compute()", {"function": "compute", "line": 1}
        )
    )
    graph.add_node(
        GraphNode(
            "compute.py::compute:block0",
            "return",
            "return",
            {"stmt": "return", "line": "13"},
        )
    )
    graph.add_node(GraphNode("compute.py::compute:end", "block", "end", {"function": "compute"}))
    graph.add_edge("compute.py::compute:start", "compute.py::compute:block0", "flows_to")
    graph.add_edge("compute.py::compute:block0", "compute.py::compute:end", "flows_to")
    return graph


def test_localize_cfg_scores_reachable_crash_line() -> None:
    """A return block carrying the crash line yields full CFG evidence."""
    engine = LocalizationEngine()
    result = engine.localize(_build_graph_with_cfg(), _build_runtime(), language="python")

    crash = next(c for c in result.candidates if c.node_id == "compute.py::compute")
    cfg = [e for e in crash.evidence if e.source == EvidenceSource.CFG]
    assert len(cfg) == 1
    assert cfg[0].score == 1.0


def test_localize_resolves_crash() -> None:
    """The raiser's writer is ranked first with hand-computable confidence."""
    engine = LocalizationEngine()
    result = engine.localize(_build_graph(), _build_runtime(), language="python")

    assert result.resolved is True
    assert result.confidence == 0.713
    assert result.root_cause is not None
    assert result.root_cause.node_id == "worker.py::worker"
    assert result.propagation_path == ["main", "worker", "compute"]
    assert result.missing_sources == ["cfg"]
    assert result.suggested_fix == (
        "Check the arguments passed by this function and how its return "
        "value is consumed at the crash site."
    )
    assert result.candidates[0].score >= result.candidates[-1].score


def test_localize_resolves_crash_with_windows_paths() -> None:
    """Windows absolute runtime paths resolve onto the same static nodes."""
    engine = LocalizationEngine()
    result = engine.localize(_build_graph(), _build_runtime_win(), language="python")

    assert result.resolved is True
    assert result.root_cause is not None
    assert result.root_cause.node_id == "worker.py::worker"
    assert result.confidence == 0.713
    assert result.propagation_path == ["main", "worker", "compute"]
    assert result.missing_sources == ["cfg"]


def test_localize_ranks_raiser_second() -> None:
    """The direct raiser carries strong runtime and stack evidence."""
    engine = LocalizationEngine()
    result = engine.localize(_build_graph(), _build_runtime(), language="python")

    raiser = next(
        candidate for candidate in result.candidates if candidate.node_id == "compute.py::compute"
    )
    sources = {item.source for item in raiser.evidence}
    assert EvidenceSource.RUNTIME_TRACE in sources
    assert EvidenceSource.STACK_TRACE in sources
    runtime_item = next(
        item for item in raiser.evidence if item.source == EvidenceSource.RUNTIME_TRACE
    )
    assert runtime_item.score == 1.0


def test_localize_threshold_miss_reports_hypotheses() -> None:
    """Below the threshold the top candidate is reported as a hypothesis."""
    engine = LocalizationEngine(threshold=0.8)
    result = engine.localize(_build_graph(), _build_runtime(), language="python")

    assert result.resolved is False
    assert result.root_cause is None
    assert result.suggested_fix is None
    assert result.candidates
    assert "Cannot determine" in result.summary


def test_localize_without_runtime_is_unresolved() -> None:
    """No crash evidence produces an empty, unresolved result."""
    engine = LocalizationEngine()
    result = engine.localize(_build_graph(), None, language="python")

    assert result.resolved is False
    assert result.confidence == 0.0
    assert result.candidates == []
    assert result.propagation_path == []
    assert result.suggested_fix is None
    assert result.missing_sources == [source.value for source in EvidenceSource]
    assert "No crash evidence" in result.summary


def test_localize_without_graph_degrades_gracefully() -> None:
    """A missing graph still anchors the crash via runtime node ids."""
    engine = LocalizationEngine()
    result = engine.localize(None, _build_runtime(), language="python")

    assert result.resolved is False
    assert result.confidence < 0.7
    assert result.candidates
    assert result.candidates[0].node_id.startswith("runtime::python::")


def test_evidence_rejects_out_of_range_score() -> None:
    """Evidence scores must stay inside [0, 1]."""
    with pytest.raises(ValueError):
        Evidence(EvidenceSource.AST, "x", 1.5)


def test_result_requires_root_cause_when_resolved() -> None:
    """A resolved result must name a root cause."""
    with pytest.raises(ValueError):
        LocalizationResult(
            resolved=True,
            confidence=0.8,
            summary="",
            root_cause=None,
            candidates=[],
            propagation_path=[],
            evidence_summary=[],
            missing_sources=[],
            suggested_fix=None,
        )


def test_scorer_weights_must_sum_to_one() -> None:
    """Custom weights that break the budget are rejected."""
    with pytest.raises(ValueError):
        ConfidenceScorer({EvidenceSource.AST: 0.5})


def test_scorer_uses_default_weights() -> None:
    """A single full-strength AST item contributes its default weight."""
    scorer = ConfidenceScorer()
    assert scorer.confidence([Evidence(EvidenceSource.AST, "x", 1.0)]) == 0.02


def test_scorer_strongest_evidence_wins_per_source() -> None:
    """Multiple items from one source never exceed that source's weight."""
    scorer = ConfidenceScorer()
    evidence = [
        Evidence(EvidenceSource.AST, "weak", 0.1),
        Evidence(EvidenceSource.AST, "strong", 1.0),
    ]
    assert scorer.confidence(evidence) == 0.02


def test_manager_stores_and_returns_record() -> None:
    """Localize then retrieve by project id."""
    manager = LocalizationManager()
    record = manager.localize("demo", _build_graph(), _build_runtime(), language="python")

    assert record.status.value == "ready"
    assert record.result is not None
    assert record.result.resolved is True

    fetched = manager.get("demo")
    assert fetched is record


def test_manager_get_unknown_project_raises() -> None:
    """Fetching an unknown project surfaces a structured error."""
    manager = LocalizationManager()
    with pytest.raises(NotFoundError):
        manager.get("missing")


def test_manager_rejects_empty_graph() -> None:
    """No evidence means no localization."""
    manager = LocalizationManager()
    with pytest.raises(ValidationError):
        manager.localize("empty", Graph(name="empty"), None, language="python")


class _ExplodingEngine(LocalizationEngine):
    """Engine stub that always fails during localization."""

    def localize(self, *args, **kwargs) -> LocalizationResult:
        raise RuntimeError("boom")


def test_manager_records_engine_failure() -> None:
    """An engine exception is captured as a failed record, not re-raised."""
    manager = LocalizationManager(engine=_ExplodingEngine())
    record = manager.localize("boom", _build_graph(), _build_runtime(), language="python")

    assert record.status.value == "failed"
    assert record.error == "boom"
    assert record.result is None
