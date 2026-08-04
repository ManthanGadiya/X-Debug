"""Localization engine.

Turns a knowledge graph plus a runtime result into a ranked list of
candidate root causes. The pipeline is deterministic and explainable:

    graph + runtime
        -> CrashContext        (what happened, where)
        -> candidate set       (who could be responsible)
        -> per-candidate evidence (why they could be)
        -> weighted confidence (docs/BUG_LOCALIZATION.md §23)
        -> ranked result       (§25 outcome)

No model is involved. The engine only reasons over the graph that the
:class:`KnowledgeGraphBuilder` produced and the events captured by the
runtime harness.
"""

from __future__ import annotations

import re
from collections import deque
from collections.abc import Sequence

from app.analysis.graph import Graph, GraphNode
from app.core.logging import StructuredLogger, get_logger
from app.localization.evidence import CrashContext, EvidenceExtractor
from app.localization.model import (
    EvidenceSource,
    LocalizationCandidate,
    LocalizationResult,
)
from app.localization.scorer import ConfidenceScorer
from app.runtime.model import RuntimeResult, TraceEvent, TraceEventType

logger = get_logger(__name__)

_DEFAULT_THRESHOLD = 0.7
_DEFAULT_LANGUAGE = "python"

_TRACEBACK_HEADER = re.compile(r"^Traceback \(most recent call last\):\s*$", re.MULTILINE)
_TRACEBACK_FRAME = re.compile(
    r'^\s*File "(?P<file>[^"]+)", line (?P<line>\d+)(?:, in (?P<function>.+))?\s*$',
    re.MULTILINE,
)


class LocalizationEngine:
    """Rank candidate root causes for a crash."""

    def __init__(
        self,
        extractor: EvidenceExtractor | None = None,
        scorer: ConfidenceScorer | None = None,
        *,
        threshold: float = _DEFAULT_THRESHOLD,
        logger: StructuredLogger = logger,
    ) -> None:
        self._extractor = extractor or EvidenceExtractor()
        self._scorer = scorer or ConfidenceScorer()
        self._threshold = threshold
        self._logger = logger

    # -- public API -----------------------------------------------------

    def localize(
        self,
        graph: Graph | None,
        runtime: RuntimeResult | None,
        language: str = _DEFAULT_LANGUAGE,
        threshold: float | None = None,
    ) -> LocalizationResult:
        """Localize the crash described by ``runtime`` against ``graph``."""
        effective_threshold = self._threshold if threshold is None else threshold
        self._extractor.prepare(graph)
        ctx = self._build_context(graph, runtime, language)
        self._compute_context_maps(graph, ctx)
        candidate_ids = self._generate_candidates(graph, ctx)
        ranked = self._rank_candidates(graph, ctx, candidate_ids)
        return self._build_result(graph, ctx, ranked, effective_threshold)

    # -- crash context --------------------------------------------------

    def _build_context(
        self,
        graph: Graph | None,
        runtime: RuntimeResult | None,
        language: str,
    ) -> CrashContext:
        ctx = CrashContext(language=language)
        if runtime is None:
            return ctx
        if runtime.exception is not None:
            ctx.exception_type = runtime.exception.type
            ctx.exception_message = runtime.exception.message
            ctx.exception_id = f"exception::{language}::{runtime.exception.type}"
        frames = self._parse_traceback(runtime.stderr or "")
        if frames:
            ctx.crash_file = frames[-1][0]
            ctx.crash_line = frames[-1][1]
            resolved = [
                (
                    file,
                    function,
                    self._extractor.resolve_function(language, file, function),
                )
                for file, _line, function in frames
            ]
            ctx.stack_trace_nodes = [
                node_id for _file, function, node_id in resolved if function != "<module>"
            ]
            if not ctx.stack_trace_nodes:
                # A module-level crash only has a <module> frame; keep it as the
                # anchor so the crash still resolves to a node.
                ctx.stack_trace_nodes = [resolved[-1][2]]
            ctx.crash_node_id = ctx.stack_trace_nodes[-1]
        elif ctx.exception_id is not None:
            # No traceback text but the runtime raised an exception: try to
            # recover the raiser from the graph's ``throws`` edges.
            raisers = self._extractor.incoming(ctx.exception_id, "throws")
            if len(raisers) == 1:
                ctx.crash_node_id = raisers[0].source
        ctx.crash_module_id = (
            self._extractor.resolve_module(language, ctx.crash_file) if ctx.crash_file else None
        )
        ctx.executed_order = self._executed_order(runtime.events or [], language)
        if ctx.crash_node_id and ctx.crash_node_id not in ctx.executed_order:
            ctx.executed_order.append(ctx.crash_node_id)
        involved_names: set[str] = set()
        for event in runtime.events or []:
            if event.type == TraceEventType.EXCEPTION:
                involved_names.update(event.variables.keys())
                break
        call_events = [e for e in runtime.events or [] if e.type == TraceEventType.CALL]
        if call_events:
            involved_names.update(call_events[-1].variables.keys())
        ctx.involved_variables = self._extractor.resolve_variables(involved_names)
        return ctx

    def _parse_traceback(self, stderr: str) -> list[tuple[str, int, str]]:
        """Return ``(file, line, function)`` frames, outermost first."""
        frames: list[tuple[str, int, str]] = []
        if not stderr:
            return frames
        header = _TRACEBACK_HEADER.search(stderr)
        if header is None:
            return frames
        block = stderr[header.end() :]
        for match in _TRACEBACK_FRAME.finditer(block):
            frames.append(
                (
                    match.group("file"),
                    int(match.group("line")),
                    (match.group("function") or "<module>").strip(),
                )
            )
        return frames

    def _executed_order(self, events: Sequence[TraceEvent], language: str) -> list[str]:
        """Deduplicated order of executed function nodes (CALL events)."""
        order: list[str] = []
        seen: set[str] = set()
        for event in events:
            if event.type != TraceEventType.CALL:
                continue
            node_id = self._extractor.resolve_function(language, event.filename, event.function)
            if node_id not in seen:
                seen.add(node_id)
                order.append(node_id)
        return order

    def _compute_context_maps(self, graph: Graph | None, ctx: CrashContext) -> None:
        """Fill the derived maps that evidence extraction depends on."""
        if ctx.crash_node_id is not None:
            ctx.read_variables = {
                edge.target for edge in self._extractor.outgoing(ctx.crash_node_id, "reads")
            }
            ctx.involved_variables.update(ctx.read_variables)
            ctx.caller_depths = self._reverse_depths(graph, ctx.crash_node_id, "calls")
            ctx.callees = {
                edge.target for edge in self._extractor.outgoing(ctx.crash_node_id, "calls")
            }
            if ctx.crash_module_id is not None:
                ctx.dependency_depths = self._reverse_depths(graph, ctx.crash_module_id, "imports")
                ctx.module_depths_by_file = dict(ctx.dependency_depths)
        for var_id in ctx.involved_variables:
            ctx.dataflow_writers[var_id] = [
                edge.source for edge in self._extractor.incoming(var_id, "writes")
            ]

    def _reverse_depths(self, graph: Graph | None, start_id: str, kind: str) -> dict[str, int]:
        """Map reachable nodes to their reverse-BFS depth from ``start_id``."""
        depths: dict[str, int] = {}
        seen = {start_id}
        pending = deque([(start_id, 0)])
        while pending:
            node_id, depth = pending.popleft()
            if depth >= 3:
                continue
            for edge in self._extractor.incoming(node_id, kind):
                if edge.source in seen:
                    continue
                seen.add(edge.source)
                child_depth = depth + 1
                depths[edge.source] = child_depth
                pending.append((edge.source, child_depth))
        return depths

    # -- candidate generation -------------------------------------------

    def _generate_candidates(self, graph: Graph | None, ctx: CrashContext) -> list[str]:
        """Return the sorted set of candidate node ids for this crash."""
        candidate_ids: set[str] = set()
        if ctx.crash_node_id:
            candidate_ids.add(ctx.crash_node_id)
        candidate_ids.update(ctx.stack_trace_nodes)
        candidate_ids.update(ctx.executed_order)
        candidate_ids.update(ctx.caller_depths.keys())
        candidate_ids.update(ctx.callees)
        candidate_ids.update(ctx.dependency_depths.keys())
        for var_id in ctx.involved_variables:
            candidate_ids.add(var_id)
            candidate_ids.update(ctx.dataflow_writers.get(var_id, []))
        return sorted(candidate_ids)

    def _rank_candidates(
        self,
        graph: Graph | None,
        ctx: CrashContext,
        candidate_ids: list[str],
    ) -> list[LocalizationCandidate]:
        ranked: list[LocalizationCandidate] = []
        for node_id in candidate_ids:
            node = self._candidate_node(graph, node_id, ctx.language or _DEFAULT_LANGUAGE)
            evidence = self._extractor.collect(node_id, ctx)
            score = self._scorer.confidence(evidence)
            best = self._scorer.best(evidence)
            reason = (
                best.description
                if best is not None
                else "Candidate is a structural neighbor of the crash area"
            )
            ranked.append(
                LocalizationCandidate(
                    node_id=node_id,
                    label=node.label or node.id,
                    kind=node.kind,
                    score=score,
                    evidence=evidence,
                    reason=reason,
                )
            )
        ranked.sort(key=lambda c: (-c.score, c.node_id))
        return ranked

    # -- result ---------------------------------------------------------

    def _build_result(
        self,
        graph: Graph | None,
        ctx: CrashContext,
        ranked: list[LocalizationCandidate],
        threshold: float,
    ) -> LocalizationResult:
        resolved = bool(ranked) and ranked[0].score >= threshold
        root_cause = ranked[0] if resolved else None
        confidence = ranked[0].score if ranked else 0.0
        evidence_summary = list(ranked[0].evidence) if ranked else []
        missing_sources = [
            source.value
            for source in EvidenceSource
            if source not in {item.source for item in evidence_summary}
        ]
        return LocalizationResult(
            resolved=resolved,
            confidence=round(confidence, 4),
            summary=self._summary(graph, ctx, ranked, resolved, confidence),
            root_cause=root_cause,
            candidates=ranked,
            propagation_path=self._propagation_path(graph, ctx),
            evidence_summary=evidence_summary,
            missing_sources=missing_sources,
            suggested_fix=self._suggested_fix(root_cause),
        )

    def _summary(
        self,
        graph: Graph | None,
        ctx: CrashContext,
        ranked: list[LocalizationCandidate],
        resolved: bool,
        confidence: float,
    ) -> str:
        if resolved and ranked:
            location = self._location(graph, ranked[0].node_id)
            return (
                f"Root cause determined: {ranked[0].label} ({location}) "
                f"with confidence {confidence:.2f}."
            )
        if ranked:
            return (
                "Cannot determine the root cause with sufficient confidence; "
                f"the top hypothesis scores {confidence:.2f} and all candidates "
                "are listed below."
            )
        return "No crash evidence was available, so no localization was produced."

    def _location(self, graph: Graph | None, node_id: str) -> str:
        node = graph.nodes.get(node_id) if graph is not None else None
        if node is None:
            return node_id
        file = node.metadata.get("file")
        line = node.metadata.get("line")
        if file and line:
            return f"{file}:{line}"
        if file:
            return str(file)
        return node_id

    def _propagation_path(self, graph: Graph | None, ctx: CrashContext) -> list[str]:
        """Human-readable chain from the entry point to the crash."""
        if ctx.stack_trace_nodes:
            return [self._label(graph, node_id) for node_id in ctx.stack_trace_nodes]
        if ctx.executed_order:
            return [self._label(graph, node_id) for node_id in ctx.executed_order[-4:]]
        return []

    def _label(self, graph: Graph | None, node_id: str) -> str:
        node = graph.nodes.get(node_id) if graph is not None else None
        if node is not None:
            return node.label or node_id
        return node_id

    def _suggested_fix(self, root_cause: LocalizationCandidate | None) -> str | None:
        """Rule-based fix guidance; no model is invoked."""
        if root_cause is None:
            return None
        best = self._scorer.best(list(root_cause.evidence))
        if best is None:
            return f"Review {root_cause.label} as a candidate contributor to the crash."
        source = best.source
        if source == EvidenceSource.DATA_FLOW:
            return (
                "Verify the data flow into the crash site: a value produced here "
                "reaches the failing expression."
            )
        if source == EvidenceSource.CALL_GRAPH:
            return (
                "Check the arguments passed by this function and how its return "
                "value is consumed at the crash site."
            )
        if source == EvidenceSource.CFG:
            return (
                "Review the branch that leads to the crash line; confirm the "
                "condition that routes execution there."
            )
        if source == EvidenceSource.DEPENDENCY_GRAPH:
            return (
                "Inspect the module boundary with the crash module for "
                "initialization or import-order issues."
            )
        if source in (EvidenceSource.STACK_TRACE, EvidenceSource.RUNTIME_TRACE):
            return "Inspect this function: it participates directly in the failing runtime path."
        return f"Review {root_cause.label} as a candidate contributor to the crash."

    # -- helpers --------------------------------------------------------

    def _candidate_node(self, graph: Graph | None, node_id: str, language: str) -> GraphNode:
        node = graph.nodes.get(node_id) if graph is not None else None
        if node is not None:
            return node
        if node_id.startswith("runtime::"):
            parts = node_id.split("::")
            filename = parts[-2] if len(parts) >= 3 else ""
            function = parts[-1]
            return GraphNode(
                id=node_id,
                kind="function",
                label=function,
                metadata={"file": filename, "runtime": True, "language": language},
            )
        if node_id.startswith("exception::"):
            exception_type = node_id.split("::")[-1]
            return GraphNode(
                id=node_id,
                kind="exception",
                label=exception_type,
                metadata={"type": exception_type},
            )
        return GraphNode(id=node_id, kind="unknown", label=node_id, metadata={})
