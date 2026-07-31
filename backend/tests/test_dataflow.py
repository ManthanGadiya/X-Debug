"""Unit tests for the data flow analyzer."""

from __future__ import annotations

from app.analysis.dataflow import DataFlowAnalyzer
from app.analysis.parsers.python import PythonParser
from app.projects.languages import Language

parser = PythonParser()


def _dfg(source: str, path: str = "main.py"):
    module = parser.parse(source, path)
    graph = DataFlowAnalyzer().build([module], {module.path: source})
    return graph


def _edges(graph, kind: str):
    return [edge for edge in graph.edges if edge.kind == kind]


def test_parameters_become_variables() -> None:
    graph = _dfg("def f(x, y):\n    return x + y\n")
    params = _edges(graph, "parameter")
    assert {edge.target for edge in params} == {"main.py::f::x", "main.py::f::y"}
    assert all(edge.source == "main.py::f" for edge in params)


def test_assignments_are_definitions() -> None:
    graph = _dfg("def f():\n    result = compute()\n    return result\n")
    defines = _edges(graph, "defines")
    assert {edge.target for edge in defines} == {"main.py::f::result"}


def test_reads_track_name_uses() -> None:
    graph = _dfg("def f(x):\n    y = x * 2\n    return y\n")
    reads = _edges(graph, "reads")
    assert {edge.target for edge in reads} == {"main.py::f::x", "main.py::f::y"}


def test_returns_link_to_variables() -> None:
    graph = _dfg("def f():\n    value = 1\n    return value\n")
    returns = _edges(graph, "returns")
    assert returns and all(edge.target == "main.py::f::value" for edge in returns)


def test_parameter_reassignment_is_both_read_and_def() -> None:
    graph = _dfg("def f(x):\n    x = x + 1\n    return x\n")
    assert _edges(graph, "defines")
    assert _edges(graph, "reads")


def test_skips_non_python_modules() -> None:
    module = parser.parse("def f():\n    pass\n", "main.py")
    module.language = Language.C
    graph = DataFlowAnalyzer().build([module], {module.path: "int f(void) {}"})
    assert graph.node_count == 0


def test_empty_function_has_no_edges() -> None:
    graph = _dfg("def f():\n    pass\n")
    assert graph.edge_count == 0
