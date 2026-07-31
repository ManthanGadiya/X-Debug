"""Unit tests for the control flow graph builder."""

from __future__ import annotations

from app.analysis.cfg import CFGBuilder
from app.analysis.parsers.python import PythonParser
from app.projects.languages import Language

parser = PythonParser()


def _cfg(source: str, path: str = "main.py"):
    module = parser.parse(source, path)
    graph = CFGBuilder().build([module], {module.path: source})
    return graph


def _edge_kinds(graph) -> set[str]:
    return {edge.kind for edge in graph.edges}


def test_linear_function_has_next_and_fallthrough() -> None:
    graph = _cfg("def f():\n" "    x = 1\n" "    y = x + 1\n" "    return y\n")
    kinds = _edge_kinds(graph)
    assert "next" in kinds
    assert "return" in kinds
    assert "fallthrough" in kinds
    assert len([e for e in graph.edges if e.kind == "return"]) == 1


def test_if_else_produces_branches() -> None:
    graph = _cfg(
        "def f(x):\n"
        "    if x > 0:\n"
        "        y = 1\n"
        "    else:\n"
        "        y = -1\n"
        "    return y\n"
    )
    kinds = _edge_kinds(graph)
    assert "branch" in kinds
    assert "true" in kinds
    assert "false" in kinds
    assert "join" in kinds


def test_while_loop_has_back_edge() -> None:
    graph = _cfg(
        "def f():\n" "    i = 0\n" "    while i < 10:\n" "        i = i + 1\n" "    return i\n"
    )
    kinds = _edge_kinds(graph)
    assert "loop" in kinds
    assert "back-edge" in kinds
    assert "true" in kinds
    assert "false" in kinds


def test_for_loop_structure() -> None:
    graph = _cfg(
        "def f(items):\n"
        "    for item in items:\n"
        "        print(item)\n"
        "    return len(items)\n"
    )
    kinds = _edge_kinds(graph)
    assert "body" in kinds
    assert "done" in kinds
    assert "back-edge" in kinds


def test_try_except_has_exception_path() -> None:
    graph = _cfg(
        "def f():\n"
        "    try:\n"
        "        x = risky()\n"
        "    except ValueError:\n"
        "        x = 0\n"
        "    return x\n"
    )
    kinds = _edge_kinds(graph)
    assert "exception" in kinds
    assert any(edge.kind == "exception" for edge in graph.edges)
    assert any(node.label.startswith("except") for node in graph.nodes.values())


def test_multiple_functions_build_independently() -> None:
    graph = _cfg(
        "def a():\n"
        "    return 1\n"
        "def b():\n"
        "    if True:\n"
        "        pass\n"
        "    return 2\n"
    )
    assert any(node.label == "a()" for node in graph.nodes.values())
    assert any(node.label == "b()" for node in graph.nodes.values())
    assert graph.node_count >= 6


def test_cfg_skips_non_python_modules() -> None:
    module = parser.parse("pass\n", "main.py")
    module.language = Language.C
    graph = CFGBuilder().build([module], {module.path: "pass\n"})
    assert graph.node_count == 0
