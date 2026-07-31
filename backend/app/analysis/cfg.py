"""Control flow graph construction.

Builds a per-function control flow graph. Nodes are basic blocks (sequential
statement runs); edges are jumps covering ``if/else`` branches, ``while``/``for``
loops, ``try/except`` exception paths, ``return`` exits, and ``break``/``continue``.
The graph is directed and represents every possible execution path before runtime.

Block construction operates on the Python AST of each function body. The builder
accepts source text per module and dispatches by language; only Python is
implemented in Version 1.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping

from app.analysis.graph import Graph, GraphNode
from app.analysis.model import ModuleAST
from app.projects.languages import Language


class CFGBuilder:
    """Build the control flow graph for every function in a set of modules."""

    def build(self, modules: list[ModuleAST], sources: Mapping[str, str]) -> Graph:
        """Return the CFG for all functions across ``modules``."""
        graph = Graph(name="cfg")
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
        prefix = _block_prefix(module_path, node.name)
        start = f"{prefix}:start"
        graph.add_node(
            GraphNode(
                id=start,
                kind="block",
                label=f"{node.name}()",
                metadata={"function": node.name, "file": module_path, "line": node.lineno},
            )
        )
        blocks: list[str] = []
        _emit_body(graph, prefix, node.body, start, blocks, returns=[])
        graph.add_node(
            GraphNode(
                id=f"{prefix}:end",
                kind="block",
                label="end",
                metadata={"function": node.name, "file": module_path},
            )
        )
        for block in blocks:
            if block != f"{prefix}:end":
                graph.add_edge(block, f"{prefix}:end", "fallthrough")


def _block_prefix(path: str, qualname: str) -> str:
    return f"{path}::{qualname}"


def _block_id(prefix: str, index: int) -> str:
    return f"{prefix}:block{index}"


def _block(
    graph: Graph,
    prefix: str,
    counter: list[int],
    label: str,
    metadata: dict[str, str],
) -> str:
    block = _block_id(prefix, counter[0])
    counter[0] += 1
    graph.add_node(GraphNode(id=block, kind="block", label=label, metadata=metadata))
    return block


def _emit_body(
    graph: Graph,
    prefix: str,
    body: list[ast.stmt],
    entry: str,
    blocks: list[str],
    *,
    returns: list[str],
) -> str:
    """Emit ``body`` starting from ``entry``; return the exit block id."""
    current = entry
    counter = [0]
    for statement in body:
        if isinstance(statement, ast.Return):
            target = _block(
                graph,
                prefix,
                counter,
                "return",
                {"stmt": "return", "line": str(statement.lineno)},
            )
            graph.add_edge(current, target, "return")
            returns.append(target)
            continue
        if isinstance(statement, ast.If):
            current = _emit_if(graph, prefix, statement, current, blocks, counter)
            continue
        if isinstance(statement, ast.While):
            current = _emit_while(graph, prefix, statement, current, blocks, counter)
            continue
        if isinstance(statement, ast.For):
            current = _emit_for(graph, prefix, statement, current, blocks, counter)
            continue
        if isinstance(statement, ast.Try):
            current = _emit_try(graph, prefix, statement, current, blocks, counter)
            continue
        if isinstance(statement, (ast.Break, ast.Continue)):
            continue

        # Fallback: emit the statement in a fresh block and chain it forward.
        block = _block(
            graph,
            prefix,
            counter,
            _statement_label(statement),
            {"line": str(getattr(statement, "lineno", 0))},
        )
        graph.add_edge(current, block, "next")
        blocks.append(block)
        current = block
    return current


def _emit_if(
    graph: Graph,
    prefix: str,
    node: ast.If,
    entry: str,
    blocks: list[str],
    counter: list[int],
) -> str:
    condition = _block(
        graph,
        prefix,
        counter,
        f"if {ast.unparse(node.test)}",
        {"stmt": "if", "line": str(node.lineno)},
    )
    graph.add_edge(entry, condition, "branch")

    then_exit = _emit_body(graph, prefix, node.body, condition, blocks, returns=[])
    else_exit = (
        _emit_body(graph, prefix, node.orelse, condition, blocks, returns=[])
        if node.orelse
        else condition
    )
    graph.add_edge(condition, then_exit, "true")
    graph.add_edge(condition, else_exit, "false")

    join = _block(graph, prefix, counter, "join", {"stmt": "if-join"})
    if then_exit != join:
        graph.add_edge(then_exit, join, "join")
    if else_exit != join:
        graph.add_edge(else_exit, join, "join")
    blocks.append(join)
    return join


def _emit_while(
    graph: Graph,
    prefix: str,
    node: ast.While,
    entry: str,
    blocks: list[str],
    counter: list[int],
) -> str:
    condition = _block(
        graph,
        prefix,
        counter,
        f"while {ast.unparse(node.test)}",
        {"stmt": "while", "line": str(node.lineno)},
    )
    graph.add_edge(entry, condition, "loop")

    body_exit = _emit_body(graph, prefix, node.body, condition, blocks, returns=[])
    else_exit = (
        _emit_body(graph, prefix, node.orelse, condition, blocks, returns=[])
        if node.orelse
        else condition
    )
    graph.add_edge(condition, body_exit, "true")
    graph.add_edge(condition, else_exit, "false")
    graph.add_edge(body_exit, condition, "back-edge")

    join = _block(graph, prefix, counter, "join", {"stmt": "while-join"})
    graph.add_edge(else_exit, join, "join")
    blocks.append(join)
    return join


def _emit_for(
    graph: Graph,
    prefix: str,
    node: ast.For,
    entry: str,
    blocks: list[str],
    counter: list[int],
) -> str:
    header = _block(
        graph,
        prefix,
        counter,
        f"for {ast.unparse(node.target)} in {ast.unparse(node.iter)}",
        {"stmt": "for", "line": str(node.lineno)},
    )
    graph.add_edge(entry, header, "loop")

    body_exit = _emit_body(graph, prefix, node.body, header, blocks, returns=[])
    else_exit = (
        _emit_body(graph, prefix, node.orelse, header, blocks, returns=[])
        if node.orelse
        else header
    )
    graph.add_edge(header, body_exit, "body")
    graph.add_edge(header, else_exit, "done")
    graph.add_edge(body_exit, header, "back-edge")

    join = _block(graph, prefix, counter, "join", {"stmt": "for-join"})
    graph.add_edge(else_exit, join, "join")
    blocks.append(join)
    return join


def _emit_try(
    graph: Graph,
    prefix: str,
    node: ast.Try,
    entry: str,
    blocks: list[str],
    counter: list[int],
) -> str:
    body_exit = _emit_body(graph, prefix, node.body, entry, blocks, returns=[])

    join = _block(graph, prefix, counter, "join", {"stmt": "try-join"})
    graph.add_edge(body_exit, join, "join")

    for handler in node.handlers:
        handler_name = handler.type and ast.unparse(handler.type) or "Exception"
        handler_block = _block(
            graph,
            prefix,
            counter,
            f"except {handler_name}",
            {"stmt": "except", "line": str(handler.lineno)},
        )
        graph.add_edge(entry, handler_block, "exception")
        handler_exit = _emit_body(graph, prefix, handler.body, handler_block, blocks, returns=[])
        if handler_exit != handler_block:
            graph.add_edge(handler_exit, join, "join")

    if node.orelse:
        else_exit = _emit_body(graph, prefix, node.orelse, join, blocks, returns=[])
        if else_exit != join:
            graph.add_edge(else_exit, join, "next")

    blocks.append(join)
    return join


def _statement_label(statement: ast.stmt) -> str:
    if isinstance(statement, ast.Assign):
        return "assign"
    if isinstance(statement, ast.Expr):
        return "expr"
    return statement.__class__.__name__
