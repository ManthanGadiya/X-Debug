"""Knowledge graph construction (Phase 5).

Merges every static and runtime analysis into one unified graph that represents
the entire project. The merge is deterministic: nodes are keyed by their stable
source identifiers (deduplicated by id), and edges carry the typed relationship
labels documented for the evidence graph (see docs/BUG_LOCALIZATION.md §6–8).

Sources, in merge order:

1. AST structure    — project, module, class, function, method and variable
                      nodes with ``defines`` containment and ``inherits`` edges.
2. Dependency graph — module nodes and ``imports`` edges.
3. Call graph       — function/external nodes and ``calls`` edges.
4. Control flow     — condition/loop/return blocks and ``flows_to`` edges.
5. Data flow        — variable nodes and ``reads``/``writes``/``returns``/
                      ``parameter`` edges (method ids reconciled to qualified ids).
6. Runtime evidence — executed functions, ``executes_after`` ordering edges, and
                      ``exception`` nodes linked by ``throws`` edges.

Any source that did not contribute is reported as missing so consumers know which
evidence a graph covers.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath

from app.analysis.graph import Graph, GraphNode
from app.analysis.model import FunctionDef, ModuleAST
from app.analysis.service import AnalysisResult
from app.core.logging import StructuredLogger, get_logger
from app.runtime.model import RuntimeResult, TraceEventType
from app.runtime.service import RuntimeAnalysis

logger = get_logger(__name__)


class KnowledgeNodeKind(StrEnum):
    """Canonical node kinds of the unified knowledge graph."""

    PROJECT = "project"
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    VARIABLE = "variable"
    CONDITION = "condition"
    LOOP = "loop"
    RETURN = "return"
    EXCEPTION = "exception"
    EXTERNAL = "external"
    BLOCK = "block"


class KnowledgeEdgeKind(StrEnum):
    """Canonical edge kinds of the unified knowledge graph."""

    CALLS = "calls"
    IMPORTS = "imports"
    DEFINES = "defines"
    INHERITS = "inherits"
    READS = "reads"
    WRITES = "writes"
    RETURNS = "returns"
    THROWS = "throws"
    EXECUTES_AFTER = "executes_after"
    FLOWS_TO = "flows_to"
    PARAMETER = "parameter"


@dataclass
class KnowledgeGraph:
    """The unified graph for one project and the sources that produced it."""

    project_id: str
    graph: Graph
    sources: list[str]
    missing_sources: list[str]

    @property
    def node_count(self) -> int:
        """Return the number of merged nodes."""
        return self.graph.node_count

    @property
    def edge_count(self) -> int:
        """Return the number of merged edges."""
        return self.graph.edge_count

    def node_kinds(self) -> dict[str, int]:
        """Return a count of nodes per canonical kind."""
        counts: dict[str, int] = {}
        for node in self.graph.nodes.values():
            counts[node.kind] = counts.get(node.kind, 0) + 1
        return counts

    def edge_kinds(self) -> dict[str, int]:
        """Return a count of edges per canonical kind."""
        counts: dict[str, int] = {}
        for edge in self.graph.edges:
            counts[edge.kind] = counts.get(edge.kind, 0) + 1
        return counts


class KnowledgeGraphBuilder:
    """Merge static and runtime analyses into a single project-wide graph."""

    _KNOWN_SOURCES = ("ast", "dependency", "callgraph", "cfg", "dataflow", "runtime")

    def __init__(self, *, logger: StructuredLogger = logger) -> None:
        self._logger = logger
        self._qualified_by_simple: dict[tuple[str, str], list[str]] = {}
        self._class_ids: dict[str, str] = {}
        self._class_names: dict[str, list[str]] = defaultdict(list)

    def build(
        self,
        project_id: str,
        analysis: AnalysisResult | None,
        runtime: RuntimeAnalysis | None,
    ) -> KnowledgeGraph:
        """Merge ``analysis`` and ``runtime`` into the unified graph."""
        graph = Graph(name="knowledge")
        contributed: set[str] = set()

        self._merge_ast(graph, project_id, analysis, contributed)
        self._merge_dependency(graph, analysis, contributed)
        self._merge_callgraph(graph, analysis, contributed)
        self._merge_cfg(graph, analysis, contributed)
        self._merge_dataflow(graph, analysis, contributed)
        self._merge_runtime(graph, runtime, contributed)

        sources = sorted(contributed)
        missing = sorted(set(self._KNOWN_SOURCES) - contributed)
        self._logger.structured(
            logging.INFO,
            "knowledge graph built",
            project_id=project_id,
            nodes=graph.node_count,
            edges=graph.edge_count,
            sources=sources,
            missing=missing,
        )
        return KnowledgeGraph(
            project_id=project_id,
            graph=graph,
            sources=sources,
            missing_sources=missing,
        )

    def _merge_ast(
        self,
        graph: Graph,
        project_id: str,
        analysis: AnalysisResult | None,
        contributed: set[str],
    ) -> None:
        if analysis is None or not analysis.modules:
            return
        contributed.add("ast")
        project_node = f"project::{project_id}"
        graph.add_node(GraphNode(id=project_node, kind=KnowledgeNodeKind.PROJECT, label=project_id))

        self._index_classes(analysis.modules)
        for module in analysis.modules:
            module_id = _module_id(module.path)
            graph.add_node(
                GraphNode(
                    id=module_id,
                    kind=KnowledgeNodeKind.MODULE,
                    label=module.path,
                    metadata={"file": module.path, "language": module.language.value},
                )
            )
            graph.add_edge(project_node, module_id, KnowledgeEdgeKind.DEFINES)

            for cls in module.classes:
                class_id = _function_id(module.path, cls.qualname)
                graph.add_node(
                    GraphNode(
                        id=class_id,
                        kind=KnowledgeNodeKind.CLASS,
                        label=cls.qualname,
                        metadata={"file": module.path, "line": cls.line},
                    )
                )
                graph.add_edge(module_id, class_id, KnowledgeEdgeKind.DEFINES)
                for base in cls.bases:
                    base_id = self._resolve_base(base)
                    if base_id is not None:
                        graph.add_edge(class_id, base_id, KnowledgeEdgeKind.INHERITS)
                for method in cls.methods:
                    method_id = _function_id(module.path, method.qualname)
                    self._index_function(module.path, method)
                    graph.add_node(
                        GraphNode(
                            id=method_id,
                            kind=KnowledgeNodeKind.METHOD,
                            label=method.qualname,
                            metadata={"file": module.path, "line": method.line},
                        )
                    )
                    graph.add_edge(class_id, method_id, KnowledgeEdgeKind.DEFINES)

            for function in module.functions:
                function_id = _function_id(module.path, function.qualname)
                self._index_function(module.path, function)
                graph.add_node(
                    GraphNode(
                        id=function_id,
                        kind=KnowledgeNodeKind.FUNCTION,
                        label=function.qualname,
                        metadata={"file": module.path, "line": function.line},
                    )
                )
                graph.add_edge(module_id, function_id, KnowledgeEdgeKind.DEFINES)

            for variable in module.variables:
                variable_id = f"{module_id}::{variable.name}"
                graph.add_node(
                    GraphNode(
                        id=variable_id,
                        kind=KnowledgeNodeKind.VARIABLE,
                        label=variable.name,
                        metadata={"file": module.path, "line": variable.line},
                    )
                )
                graph.add_edge(module_id, variable_id, KnowledgeEdgeKind.DEFINES)

    def _merge_dependency(
        self,
        graph: Graph,
        analysis: AnalysisResult | None,
        contributed: set[str],
    ) -> None:
        source = analysis.dependency_graph if analysis else None
        if source is None:
            return
        contributed.add("dependency")
        _add_nodes(graph, source)
        for edge in source.edges:
            graph.add_edge(edge.source, edge.target, KnowledgeEdgeKind.IMPORTS)

    def _merge_callgraph(
        self,
        graph: Graph,
        analysis: AnalysisResult | None,
        contributed: set[str],
    ) -> None:
        source = analysis.call_graph if analysis else None
        if source is None:
            return
        contributed.add("callgraph")
        _add_nodes(graph, source)
        for edge in source.edges:
            graph.add_edge(edge.source, edge.target, KnowledgeEdgeKind.CALLS)

    def _merge_cfg(
        self,
        graph: Graph,
        analysis: AnalysisResult | None,
        contributed: set[str],
    ) -> None:
        source = analysis.cfg if analysis else None
        if source is None:
            return
        contributed.add("cfg")
        for node in source.nodes.values():
            graph.add_node(
                GraphNode(
                    id=node.id,
                    kind=_block_kind(node),
                    label=node.label,
                    metadata=node.metadata,
                )
            )
        for edge in source.edges:
            graph.add_edge(edge.source, edge.target, KnowledgeEdgeKind.FLOWS_TO)

    def _merge_dataflow(
        self,
        graph: Graph,
        analysis: AnalysisResult | None,
        contributed: set[str],
    ) -> None:
        source = analysis.dataflow_graph if analysis else None
        if source is None:
            return
        contributed.add("dataflow")
        for node in source.nodes.values():
            if node.kind == "function":
                graph.add_node(
                    GraphNode(
                        id=self._reconcile_dataflow_id(node.id),
                        kind=KnowledgeNodeKind.FUNCTION,
                        label=node.label,
                        metadata=node.metadata,
                    )
                )
            elif node.kind == "variable":
                graph.add_node(
                    GraphNode(
                        id=self._reconcile_dataflow_id(node.id),
                        kind=KnowledgeNodeKind.VARIABLE,
                        label=node.label,
                    )
                )
            else:
                graph.add_node(
                    GraphNode(id=node.id, kind=node.kind, label=node.label, metadata=node.metadata)
                )
        for edge in source.edges:
            graph.add_edge(
                self._reconcile_dataflow_id(edge.source),
                self._reconcile_dataflow_id(edge.target),
                _dataflow_edge_kind(edge.kind),
            )

    def _merge_runtime(
        self,
        graph: Graph,
        runtime: RuntimeAnalysis | None,
        contributed: set[str],
    ) -> None:
        if runtime is None or not runtime.results:
            return
        index = _runtime_function_index(graph)
        contributed_runtime = False
        for language, result in sorted(runtime.results.items()):
            if not result.events and result.exception is None:
                continue
            contributed_runtime = True
            executed = self._execution_sequence(graph, language, result, index)
            _add_executes_after(graph, executed)
            if result.exception is not None:
                self._add_exception(graph, language, result, executed, index)
        if contributed_runtime:
            contributed.add("runtime")

    def _index_classes(self, modules: list[ModuleAST]) -> None:
        for module in modules:
            for cls in module.classes:
                class_id = _function_id(module.path, cls.qualname)
                self._class_ids[cls.qualname] = class_id
                self._class_names[cls.name].append(class_id)

    def _index_function(self, module_path: str, function: FunctionDef) -> None:
        simple = function.qualname.rsplit(".", 1)[-1]
        self._qualified_by_simple.setdefault((module_path, simple), []).append(
            _function_id(module_path, function.qualname)
        )

    def _resolve_base(self, base: str) -> str | None:
        """Resolve ``base`` to a project class id when unambiguous."""
        if base in self._class_ids:
            return self._class_ids[base]
        candidates = self._class_names.get(base, [])
        return candidates[0] if len(candidates) == 1 else None

    def _reconcile_dataflow_id(self, node_id: str) -> str:
        """Map a dataflow id onto its qualified AST/call graph counterpart."""
        parts = node_id.split("::")
        if len(parts) == 2:
            file, name = parts
            return self._reconcile(file, name, node_id)
        if len(parts) == 3:
            file, function_name, variable_name = parts
            function_id = self._reconcile(file, function_name, f"{file}::{function_name}")
            return f"{function_id}::{variable_name}"
        return node_id

    def _reconcile(self, file: str, simple_name: str, fallback: str) -> str:
        candidates = self._qualified_by_simple.get((file, simple_name), [])
        return candidates[0] if len(candidates) == 1 else fallback

    def _execution_sequence(
        self,
        graph: Graph,
        language: str,
        result: RuntimeResult,
        index: dict[str, list[tuple[str, str | None]]],
    ) -> list[str]:
        sequence: list[str] = []
        for event in result.events:
            if event.type != TraceEventType.CALL:
                continue
            resolved = _resolve_runtime_function(
                language, event.filename, event.function, index, graph
            )
            graph.nodes[resolved].metadata["executed"] = True
            if not sequence or sequence[-1] != resolved:
                sequence.append(resolved)
        return sequence

    def _add_exception(
        self,
        graph: Graph,
        language: str,
        result: RuntimeResult,
        executed: list[str],
        index: dict[str, list[tuple[str, str | None]]],
    ) -> None:
        exception = result.exception
        if exception is None:
            return
        exception_id = f"exception::{language}::{exception.type}"
        graph.add_node(
            GraphNode(
                id=exception_id,
                kind=KnowledgeNodeKind.EXCEPTION,
                label=exception.type,
                metadata={"language": language, "message": exception.message},
            )
        )
        raiser = self._raiser_function(language, result, executed, index, graph)
        if raiser is not None:
            graph.add_edge(raiser, exception_id, KnowledgeEdgeKind.THROWS)

    def _raiser_function(
        self,
        language: str,
        result: RuntimeResult,
        executed: list[str],
        index: dict[str, list[tuple[str, str | None]]],
        graph: Graph,
    ) -> str | None:
        for event in reversed(result.events):
            if event.type == TraceEventType.EXCEPTION:
                return _resolve_runtime_function(
                    language, event.filename, event.function, index, graph
                )
        return executed[-1] if executed else None


def _add_nodes(graph: Graph, source: Graph) -> None:
    for node in source.nodes.values():
        graph.add_node(
            GraphNode(
                id=node.id,
                kind=_canonical_kind(node.kind),
                label=node.label,
                metadata=node.metadata,
            )
        )


def _canonical_kind(kind: str) -> str:
    """Map a source graph kind onto the canonical knowledge graph vocabulary."""
    return _GRAPH_KIND_MAP.get(kind, kind)


_GRAPH_KIND_MAP = {
    "file": KnowledgeNodeKind.MODULE,
    "function": KnowledgeNodeKind.FUNCTION,
    "external": KnowledgeNodeKind.EXTERNAL,
    "variable": KnowledgeNodeKind.VARIABLE,
    "block": KnowledgeNodeKind.BLOCK,
}


def _block_kind(node: GraphNode) -> str:
    """Derive a canonical kind from a CFG block's statement metadata."""
    stmt = node.metadata.get("stmt")
    if stmt == "if":
        return KnowledgeNodeKind.CONDITION
    if stmt in ("while", "for"):
        return KnowledgeNodeKind.LOOP
    if stmt == "return" or node.label == "return":
        return KnowledgeNodeKind.RETURN
    return KnowledgeNodeKind.BLOCK


def _dataflow_edge_kind(kind: str) -> str:
    """Map a data flow edge kind onto the canonical vocabulary."""
    return _DATAFLOW_EDGE_MAP.get(kind, kind)


_DATAFLOW_EDGE_MAP = {
    "defines": KnowledgeEdgeKind.WRITES,
    "reads": KnowledgeEdgeKind.READS,
    "returns": KnowledgeEdgeKind.RETURNS,
    "parameter": KnowledgeEdgeKind.PARAMETER,
}


def _runtime_function_index(
    graph: Graph,
) -> dict[str, list[tuple[str, str | None]]]:
    """Map simple function names to ``(node_id, file)`` pairs."""
    index: dict[str, list[tuple[str, str | None]]] = defaultdict(list)
    for node in graph.nodes.values():
        if node.kind not in (KnowledgeNodeKind.FUNCTION, KnowledgeNodeKind.METHOD):
            continue
        simple = node.label.rsplit(".", 1)[-1]
        index[simple].append((node.id, node.metadata.get("file")))
    return index


def _resolve_runtime_function(
    language: str,
    filename: str,
    function: str,
    index: dict[str, list[tuple[str, str | None]]],
    graph: Graph,
) -> str:
    """Link a runtime function to a static node, or record a runtime-only node."""
    candidates = [
        node_id
        for node_id, file in index.get(function, [])
        if file is not None and _same_source(file, filename)
    ]
    if len(candidates) == 1:
        return candidates[0]
    runtime_id = f"runtime::{language}::{filename}::{function}"
    graph.add_node(
        GraphNode(
            id=runtime_id,
            kind=KnowledgeNodeKind.FUNCTION,
            label=function,
            metadata={"file": filename, "language": language, "runtime": True},
        )
    )
    return runtime_id


def _same_source(file: str, filename: str) -> bool:
    """Compare a stored source path with a runtime filename across separators."""
    if file == filename:
        return True
    normalized_file = file.replace("\\", "/")
    normalized_filename = filename.replace("\\", "/")
    return normalized_file.endswith(
        f"/{normalized_filename}"
    ) or normalized_filename.endswith(f"/{normalized_file}")


def _add_executes_after(graph: Graph, sequence: Iterable[str]) -> None:
    previous: str | None = None
    for current in sequence:
        if previous is not None:
            graph.add_edge(previous, current, KnowledgeEdgeKind.EXECUTES_AFTER)
        previous = current


def _module_id(path: str) -> str:
    return PurePosixPath(path).as_posix()


def _function_id(path: str, qualname: str) -> str:
    return f"{path}::{qualname}"
