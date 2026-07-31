"""Unit tests for the dependency graph builder."""

from __future__ import annotations

from app.analysis.dependency import DependencyGraphBuilder
from app.analysis.parsers.python import PythonParser

parser = PythonParser()


def _module(source: str, path: str):
    return parser.parse(source, path)


def test_simple_import_creates_edge() -> None:
    modules = [
        _module("import api\n", "main.py"),
        _module("def handler():\n    pass\n", "api.py"),
    ]
    graph = DependencyGraphBuilder().build(modules)
    assert graph.edge_count == 1
    (edge,) = graph.edges
    assert edge.source == "main.py"
    assert edge.target == "api.py"
    assert edge.kind == "imports"


def test_package_import_resolves_to_file() -> None:
    modules = [
        _module("from pkg.mod import thing\n", "main.py"),
        _module("def thing():\n    pass\n", "pkg/mod.py"),
    ]
    graph = DependencyGraphBuilder().build(modules)
    assert graph.edge_count == 1
    (edge,) = graph.edges
    assert edge.source == "main.py"
    assert edge.target == "pkg/mod.py"


def test_unknown_import_creates_no_edge() -> None:
    modules = [_module("import requests\n", "main.py")]
    graph = DependencyGraphBuilder().build(modules)
    assert graph.edge_count == 0
    assert graph.node_count == 1


def test_multi_level_import_resolves_longest_match() -> None:
    modules = [
        _module("import pkg.sub.mod\n", "main.py"),
        _module("pass\n", "pkg/__init__.py"),
        _module("pass\n", "pkg/sub/__init__.py"),
        _module("x = 1\n", "pkg/sub/mod.py"),
    ]
    graph = DependencyGraphBuilder().build(modules)
    (edge,) = graph.edges
    assert edge.target == "pkg/sub/mod.py"


def test_duplicate_imports_are_deduplicated() -> None:
    modules = [
        _module("import api\nimport api\n", "main.py"),
        _module("pass\n", "api.py"),
    ]
    graph = DependencyGraphBuilder().build(modules)
    assert graph.edge_count == 1


def test_c_include_resolves_to_project_file() -> None:
    from app.analysis.parsers.c import CParser

    c_parser = CParser()
    modules = [
        c_parser.parse('#include "mylib.h"\n', "main.c"),
        c_parser.parse("int helper(void);\n", "mylib.h"),
    ]
    graph = DependencyGraphBuilder().build(modules)
    (edge,) = graph.edges
    assert edge.source == "main.c"
    assert edge.target == "mylib.h"
    assert edge.kind == "imports"


def test_system_include_creates_no_edge() -> None:
    from app.analysis.parsers.c import CParser

    c_parser = CParser()
    modules = [c_parser.parse("#include <stdio.h>\n", "main.c")]
    graph = DependencyGraphBuilder().build(modules)
    assert graph.edge_count == 0
    assert graph.node_count == 1
