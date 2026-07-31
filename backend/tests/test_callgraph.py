"""Unit tests for the call graph builder."""

from __future__ import annotations

from app.analysis.callgraph import CallGraphBuilder
from app.analysis.parsers.python import PythonParser

parser = PythonParser()


def _module(source: str, path: str):
    return parser.parse(source, path)


def test_calls_between_functions() -> None:
    modules = [
        _module(
            "def main():\n    return helper()\ndef helper():\n    return 1\n",
            "main.py",
        )
    ]
    graph = CallGraphBuilder().build(modules)
    (edge,) = graph.edges
    assert edge.source == "main.py::main"
    assert edge.target == "main.py::helper"
    assert edge.kind == "calls"


def test_method_calls_resolve_within_class() -> None:
    modules = [
        _module(
            "class Service:\n"
            "    def run(self):\n"
            "        return self._work()\n"
            "    def _work(self):\n"
            "        pass\n",
            "service.py",
        )
    ]
    graph = CallGraphBuilder().build(modules)
    assert any(
        edge.source == "service.py::Service.run" and edge.target == "service.py::Service._work"
        for edge in graph.edges
    )


def test_external_call_is_recorded() -> None:
    modules = [_module("def main():\n    return len([])\n", "main.py")]
    graph = CallGraphBuilder().build(modules)
    (edge,) = graph.edges
    assert edge.source == "main.py::main"
    assert edge.target == "external::len"
    assert edge.kind == "calls"


def test_call_targets_across_files_resolve_by_name() -> None:
    modules = [
        _module("def main():\n    return render()\n", "app/main.py"),
        _module("def render():\n    return 'x'\n", "app/ui.py"),
    ]
    graph = CallGraphBuilder().build(modules)
    (edge,) = graph.edges
    assert edge.source == "app/main.py::main"
    assert edge.target == "app/ui.py::render"


def test_node_count_includes_all_functions() -> None:
    modules = [
        _module(
            "def a():\n    pass\ndef b():\n    pass\nclass C:\n    def m(self):\n        pass\n",
            "mod.py",
        )
    ]
    graph = CallGraphBuilder().build(modules)
    function_nodes = [node for node in graph.nodes.values() if node.kind == "function"]
    assert len(function_nodes) == 3
