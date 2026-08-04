"""Per-source evidence extraction for localization candidates.

Each ``_evidence_for`` method answers one question for one candidate node:

* Stack trace — where does the candidate sit relative to the crash?
* Runtime trace — was the candidate executed / did it raise the exception?
* Data flow — does data written by the candidate reach the crash site?
* CFG — is the crash line reachable in the candidate's control flow?
* Call graph — is the candidate a caller (or callee) of the crash function?
* Dependency graph — does the candidate's module import the crash module?
* AST — is the candidate part of the project's static model?

Sources that produce no evidence for a candidate return ``None``; the engine
records them as *missing* so the final report can explain why a candidate
scored the way it did (docs/BUG_LOCALIZATION.md §25).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from app.analysis.graph import Graph, GraphEdge, GraphNode
from app.localization.model import Evidence, EvidenceSource

_FUNCTION_KINDS = ("function", "method")
_STATIC_KINDS = ("module", "class", "function", "method", "variable")

# The knowledge builder canonicalizes CFG statement blocks onto these kinds
# (app/analysis/knowledge.py ``_block_kind``); all of them belong to a
# function's control-flow region and must be indexed for CFG evidence.
_CFG_KINDS = frozenset({"block", "condition", "loop", "return"})

# Reverse-BFS depth -> evidence score for callers / importers.
_CALLER_SCORES = {1: 1.0, 2: 0.7, 3: 0.5}
_IMPORTER_SCORES = {1: 0.8, 2: 0.5, 3: 0.3}
_IMPORTER_FUNCTION_SCORES = {1: 0.6, 2: 0.4, 3: 0.2}


@dataclass
class CrashContext:
    """Facts about the crash that evidence extraction reasons over.

    The engine computes this once per localization run; the extractor is
    stateless with respect to the crash so evidence stays deterministic.
    """

    language: str | None = None
    exception_type: str | None = None
    exception_message: str | None = None
    exception_id: str | None = None
    crash_node_id: str | None = None
    crash_file: str | None = None
    crash_line: int | None = None
    crash_module_id: str | None = None
    # Outermost -> innermost (crash last).
    stack_trace_nodes: list[str] = field(default_factory=list)
    # Execution order (deduplicated) of resolved function nodes.
    executed_order: list[str] = field(default_factory=list)
    # Variable node ids observed in the crash frame or read by the crash fn.
    involved_variables: set[str] = field(default_factory=set)
    # Variable node ids read by the crash function (via ``reads`` edges).
    read_variables: set[str] = field(default_factory=set)
    # Variable node id -> writer function node ids (via ``writes`` edges).
    dataflow_writers: dict[str, list[str]] = field(default_factory=dict)
    # Function node id -> reverse-BFS depth over ``calls`` edges from crash.
    caller_depths: dict[str, int] = field(default_factory=dict)
    # Direct callees of the crash function.
    callees: set[str] = field(default_factory=set)
    # Module node id -> reverse-BFS depth over ``imports`` edges from crash.
    dependency_depths: dict[str, int] = field(default_factory=dict)
    # Posix module path -> dependency depth (for function candidates).
    module_depths_by_file: dict[str, int] = field(default_factory=dict)


def _simple_name(label: str) -> str:
    """Return the trailing component of a qualified label."""
    return label.rsplit(".", 1)[-1]


def _posix(path: str) -> str:
    """Normalize a file path for comparison."""
    return PurePosixPath(path).as_posix()


def _same_source(file: str, filename: str) -> bool:
    r"""Compare a stored source path with a runtime filename across separators.

    Static analysis stores project-relative paths (``compute.py``) while the
    runtime harness reports absolute filesystem paths (``C:\\repo\\compute.py``
    on Windows). Normalize both to posix separators before suffix matching.
    """
    if file == filename:
        return True
    normalized_file = file.replace("\\", "/")
    normalized_filename = filename.replace("\\", "/")
    return normalized_file.endswith(f"/{normalized_filename}") or normalized_filename.endswith(
        f"/{normalized_file}"
    )


def _basename(path: str) -> str:
    """Return the file component of a path, tolerating either separator."""
    return PurePosixPath(path.replace("\\", "/")).name


class EvidenceExtractor:
    """Extract scored evidence for candidates from the knowledge graph."""

    def __init__(self) -> None:
        self._graph: Graph | None = None
        self._out: dict[str, list[GraphEdge]] = defaultdict(list)
        self._in: dict[str, list[GraphEdge]] = defaultdict(list)
        self._function_index: dict[str, list[tuple[str, str | None]]] = defaultdict(list)
        self._module_index: dict[str, list[str]] = defaultdict(list)
        self._variable_ids_by_name: dict[str, list[str]] = defaultdict(list)
        self._writers: dict[str, list[str]] = defaultdict(list)
        self._blocks: dict[str, list[GraphNode]] = defaultdict(list)

    def prepare(self, graph: Graph | None) -> None:
        """Index ``graph`` once per localization run."""
        self._graph = graph
        self._out.clear()
        self._in.clear()
        self._function_index.clear()
        self._module_index.clear()
        self._variable_ids_by_name.clear()
        self._writers.clear()
        self._blocks.clear()
        if graph is None:
            return
        for node in graph.nodes.values():
            if node.kind in _FUNCTION_KINDS:
                self._function_index[_simple_name(node.label)].append(
                    (node.id, node.metadata.get("file"))
                )
            elif node.kind == "module":
                self._module_index[_basename(node.id)].append(node.id)
            elif node.kind == "variable":
                self._variable_ids_by_name[node.label].append(node.id)
            elif node.kind in _CFG_KINDS:
                function_id = node.id.rsplit(":", 1)[0]
                self._blocks[function_id].append(node)
        for edge in graph.edges:
            self._out[edge.source].append(edge)
            self._in[edge.target].append(edge)
            if edge.kind == "writes":
                self._writers[edge.target].append(edge.source)

    # -- public API -----------------------------------------------------

    def resolve_function(self, language: str, filename: str, function: str) -> str:
        """Link a runtime function name to a static node id when unambiguous.

        Mirrors ``knowledge._resolve_runtime_function``; the fallback id is
        never created here because the engine does not mutate the graph.
        """
        candidates = [
            node_id
            for node_id, file in self._function_index.get(function, [])
            if file is not None and _same_source(file, filename)
        ]
        if len(candidates) == 1:
            return candidates[0]
        return f"runtime::{language}::{filename}::{function}"

    def resolve_module(self, language: str, filename: str) -> str:
        """Link a runtime crash file to a static module node id.

        Module node ids are project-relative (``compute.py``), so the runtime
        absolute path is matched by basename. An ambiguous basename (the same
        file name in two directories) falls back to the posix path, which keeps
        the previous (unresolved) behavior for that rare case.
        """
        candidates = self._module_index.get(_basename(filename), [])
        if len(candidates) == 1:
            return candidates[0]
        return _posix(filename)

    def resolve_variables(self, names: set[str]) -> set[str]:
        """Resolve runtime variable names to knowledge graph variable ids."""
        resolved: set[str] = set()
        for name in names:
            resolved.update(self._variable_ids_by_name.get(name, []))
        return resolved

    def outgoing(self, node_id: str, kind: str | None = None) -> list[GraphEdge]:
        """Return edges leaving ``node_id``, optionally filtered by kind."""
        edges = self._out.get(node_id, [])
        if kind is None:
            return list(edges)
        return [edge for edge in edges if edge.kind == kind]

    def incoming(self, node_id: str, kind: str | None = None) -> list[GraphEdge]:
        """Return edges entering ``node_id``, optionally filtered by kind."""
        edges = self._in.get(node_id, [])
        if kind is None:
            return list(edges)
        return [edge for edge in edges if edge.kind == kind]

    def collect(self, node_id: str, ctx: CrashContext) -> list[Evidence]:
        """Collect evidence for ``node_id`` from every source."""
        evidence: list[Evidence] = []
        for source in EvidenceSource:
            item = self._evidence_for(source, node_id, ctx)
            if item is not None:
                evidence.append(item)
        return evidence

    # -- dispatch -------------------------------------------------------

    def _evidence_for(
        self, source: EvidenceSource, node_id: str, ctx: CrashContext
    ) -> Evidence | None:
        if source == EvidenceSource.STACK_TRACE:
            return self._stack_trace_evidence(node_id, ctx)
        if source == EvidenceSource.RUNTIME_TRACE:
            return self._runtime_trace_evidence(node_id, ctx)
        if source == EvidenceSource.DATA_FLOW:
            return self._data_flow_evidence(node_id, ctx)
        if source == EvidenceSource.CFG:
            return self._cfg_evidence(node_id, ctx)
        if source == EvidenceSource.CALL_GRAPH:
            return self._call_graph_evidence(node_id, ctx)
        if source == EvidenceSource.DEPENDENCY_GRAPH:
            return self._dependency_evidence(node_id, ctx)
        return self._ast_evidence(node_id, ctx)

    # -- per-source extractors ------------------------------------------

    def _stack_trace_evidence(self, node_id: str, ctx: CrashContext) -> Evidence | None:
        if not ctx.stack_trace_nodes or node_id not in ctx.stack_trace_nodes:
            return None
        position = len(ctx.stack_trace_nodes) - 1 - ctx.stack_trace_nodes.index(node_id)
        score = round(max(0.2, 1.0 - 0.2 * position), 4)
        return Evidence(
            EvidenceSource.STACK_TRACE,
            f"Present in the crash stack trace ({position} frame(s) from the crash)",
            score,
        )

    def _runtime_trace_evidence(self, node_id: str, ctx: CrashContext) -> Evidence | None:
        if ctx.crash_node_id and node_id == ctx.crash_node_id:
            return Evidence(
                EvidenceSource.RUNTIME_TRACE,
                "Raised the observed exception at runtime",
                1.0,
            )
        if node_id in ctx.executed_order:
            position = len(ctx.executed_order) - 1 - ctx.executed_order.index(node_id)
            if position <= 3:
                return Evidence(
                    EvidenceSource.RUNTIME_TRACE,
                    f"Executed {position} call(s) before the crash",
                    round(max(0.3, 1.0 - 0.25 * position), 4),
                )
            return None
        if node_id in ctx.involved_variables:
            return Evidence(
                EvidenceSource.RUNTIME_TRACE,
                "Variable value observed in the crash frame",
                0.7,
            )
        return None

    def _data_flow_evidence(self, node_id: str, ctx: CrashContext) -> Evidence | None:
        node = self._node(node_id)
        if node is not None and node.kind in _FUNCTION_KINDS:
            direct = [
                var_id
                for var_id in ctx.read_variables
                if node_id in ctx.dataflow_writers.get(var_id, [])
            ]
            if direct:
                return Evidence(
                    EvidenceSource.DATA_FLOW,
                    "Writes a value read by the crash function",
                    1.0,
                )
            involved = [
                var_id
                for var_id in ctx.involved_variables
                if node_id in ctx.dataflow_writers.get(var_id, [])
            ]
            if involved:
                return Evidence(
                    EvidenceSource.DATA_FLOW,
                    "Writes a value involved in the crash frame",
                    0.8,
                )
            return None
        if node_id in ctx.read_variables:
            return Evidence(
                EvidenceSource.DATA_FLOW,
                "Value is read by the crash function",
                1.0,
            )
        if node_id in ctx.involved_variables:
            return Evidence(
                EvidenceSource.DATA_FLOW,
                "Value is involved in the crash frame",
                0.8,
            )
        return None

    def _cfg_evidence(self, node_id: str, ctx: CrashContext) -> Evidence | None:
        if node_id not in self._blocks:
            return None
        if ctx.crash_line is not None and self._crash_line_in_blocks(node_id, ctx.crash_line):
            if self._crash_line_reachable(node_id, ctx.crash_line):
                return Evidence(
                    EvidenceSource.CFG,
                    f"Crash line {ctx.crash_line} is reachable in this candidate's control flow",
                    1.0,
                )
            return Evidence(
                EvidenceSource.CFG,
                "Candidate contains the crash line but not on a reachable path",
                0.3,
            )
        if ctx.crash_node_id and node_id == ctx.crash_node_id:
            return Evidence(
                EvidenceSource.CFG,
                "Candidate's control flow covers the crash area",
                0.8,
            )
        return None

    def _call_graph_evidence(self, node_id: str, ctx: CrashContext) -> Evidence | None:
        if ctx.crash_node_id and node_id == ctx.crash_node_id:
            return None
        depth = ctx.caller_depths.get(node_id)
        if depth is not None and depth in _CALLER_SCORES:
            hops = depth - 1
            detail = (
                "calls the crash function directly"
                if hops == 0
                else (f"reaches the crash function through {hops} intermediate call(s)")
            )
            return Evidence(
                EvidenceSource.CALL_GRAPH,
                f"Statically calls or {detail}",
                _CALLER_SCORES[depth],
            )
        if node_id in ctx.callees:
            return Evidence(
                EvidenceSource.CALL_GRAPH,
                "Called by the crash function; its return value may propagate to the crash",
                0.7,
            )
        return None

    def _dependency_evidence(self, node_id: str, ctx: CrashContext) -> Evidence | None:
        if node_id in ctx.dependency_depths:
            depth = ctx.dependency_depths[node_id]
            if depth in _IMPORTER_SCORES:
                detail = (
                    "imports the crash module directly"
                    if depth == 1
                    else (f"imports the crash module transitively ({depth - 1} hop(s))")
                )
                return Evidence(
                    EvidenceSource.DEPENDENCY_GRAPH,
                    f"Module {detail}",
                    _IMPORTER_SCORES[depth],
                )
            return None
        node = self._node(node_id)
        if node is not None and node.kind in _FUNCTION_KINDS and node.metadata.get("file"):
            module_depth = ctx.module_depths_by_file.get(_posix(str(node.metadata["file"])))
            if module_depth is not None and module_depth in _IMPORTER_FUNCTION_SCORES:
                detail = (
                    "imports the crash module directly"
                    if module_depth == 1
                    else (f"imports the crash module transitively ({module_depth - 1} hop(s))")
                )
                return Evidence(
                    EvidenceSource.DEPENDENCY_GRAPH,
                    f"Defined in a module that {detail}",
                    _IMPORTER_FUNCTION_SCORES[module_depth],
                )
        return None

    def _ast_evidence(self, node_id: str, ctx: CrashContext) -> Evidence | None:
        node = self._node(node_id)
        if node is None or node.kind not in _STATIC_KINDS:
            return None
        if node.metadata.get("runtime"):
            return None
        file = node.metadata.get("file")
        if file and ctx.crash_file and _same_source(str(file), ctx.crash_file):
            return Evidence(
                EvidenceSource.AST,
                "Static model entity in the crash module",
                0.7,
            )
        return Evidence(
            EvidenceSource.AST,
            "Static model entity on the failing path",
            0.5,
        )

    # -- helpers --------------------------------------------------------

    def _node(self, node_id: str) -> GraphNode | None:
        if self._graph is None:
            return None
        return self._graph.nodes.get(node_id)

    def _crash_line_in_blocks(self, function_id: str, crash_line: int) -> bool:
        return any(
            str(block.metadata.get("line")) == str(crash_line)
            for block in self._blocks.get(function_id, [])
        )

    def _crash_line_reachable(self, function_id: str, crash_line: int) -> bool:
        """Return True when the crash line is on a path from the function entry."""
        if self._graph is None:
            return False
        prefix = f"{function_id}:"
        start = f"{function_id}:start"
        if start not in self._graph.nodes:
            return False
        seen = {start}
        pending = [start]
        while pending:
            node_id = pending.pop()
            node = self._graph.nodes[node_id]
            if str(node.metadata.get("line")) == str(crash_line):
                return True
            for edge in self._out.get(node_id, []):
                target = edge.target
                if target.startswith(prefix) and target not in seen:
                    seen.add(target)
                    pending.append(target)
        return False
