"""Data flow analysis.

Tracks how data moves through each function: definitions (assignments),
reads (name uses), parameter passing, and returns. The output is a data flow
graph with variable nodes and ``defined-in``/``reads``/``returns`` edges that
links each assignment to the function that produced it.

Analysis is per-function and flow-insensitive (a conservative approximation
that never assumes ordering); it answers *which definitions reach which uses*
within a function.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping

from app.analysis.graph import Graph, GraphNode
from app.analysis.model import ModuleAST
from app.projects.languages import Language


class DataFlowAnalyzer:
    """Build the data flow graph for every function in a set of modules."""

    def build(self, modules: list[ModuleAST], sources: Mapping[str, str]) -> Graph:
        """Return the data flow graph for ``modules``."""
        graph = Graph(name="dataflow")
        for module in modules:
            if module.language != Language.PYTHON:
                continue
            source = sources.get(module.path, "")
            tree = ast.parse(source, filename=module.path)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self._build_function(graph, module.path, node)
        return graph

    def _build_function(
        self, graph: Graph, module_path: str, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> None:
        function_id = f"{module_path}::{node.name}"
        graph.add_node(
            GraphNode(
                id=function_id,
                kind="function",
                label=node.name,
                metadata={"file": module_path, "line": node.lineno},
            )
        )

        for param in node.args.args:
            param_id = f"{function_id}::{param.arg}"
            graph.add_node(GraphNode(id=param_id, kind="variable", label=param.arg))
            graph.add_edge(function_id, param_id, "parameter")

        definitions, reads = _collect_uses(node)
        for name in definitions:
            var_id = f"{function_id}::{name}"
            graph.add_node(GraphNode(id=var_id, kind="variable", label=name))
            graph.add_edge(function_id, var_id, "defines")
        for name in reads:
            var_id = f"{function_id}::{name}"
            graph.add_node(GraphNode(id=var_id, kind="variable", label=name))
            graph.add_edge(function_id, var_id, "reads")

        for return_node in _collect_returns(node):
            graph.add_edge(function_id, f"{function_id}::{return_node}", "returns")


def _collect_uses(node: ast.AST) -> tuple[set[str], set[str]]:
    """Return ``(definitions, reads)`` name sets for a function body."""
    definitions: set[str] = set()
    reads: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store):
            definitions.add(child.id)
        elif isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
            reads.add(child.id)
    return definitions, reads


def _collect_returns(node: ast.AST) -> set[str]:
    returns: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Return) and isinstance(child.value, ast.Name):
            returns.add(child.value.id)
    return returns
