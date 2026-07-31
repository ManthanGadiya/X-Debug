"""Dependency graph construction.

Builds the module-level dependency graph from parsed modules. Nodes are files
(or packages); edges are ``imports`` relationships between them. The graph is
directed: ``A --imports--> B`` means module A imports module B.

Resolution is deterministic and conservative: an import is resolved to another
project file when the imported module name matches a project module path,
otherwise the target is recorded as an unresolved external module.
"""

from __future__ import annotations

from pathlib import PurePosixPath

from app.analysis.graph import Graph, GraphNode
from app.analysis.model import ModuleAST


class DependencyGraphBuilder:
    """Build the dependency graph for a set of parsed modules."""

    def build(self, modules: list[ModuleAST]) -> Graph:
        """Return the dependency graph for ``modules``."""
        graph = Graph(name="dependency")

        module_index = _module_index(modules)
        for module in modules:
            graph.add_node(GraphNode(id=_file_id(module.path), kind="file", label=module.path))
            for import_record in module.imports:
                target = _resolve_import(import_record.module, module_index)
                if target is not None:
                    graph.add_node(
                        GraphNode(id=_file_id(target.path), kind="file", label=target.path)
                    )
                    graph.add_edge(
                        _file_id(module.path),
                        _file_id(target.path),
                        "imports",
                    )

        return graph


def _module_index(modules: list[ModuleAST]) -> dict[str, ModuleAST]:
    index: dict[str, ModuleAST] = {}
    for module in modules:
        stem = module.path[:-3] if module.path.endswith(".py") else module.path
        index[stem] = module
        index[module.path] = module
    return index


def _resolve_import(module_name: str, index: dict[str, ModuleAST]) -> ModuleAST | None:
    parts = module_name.split(".")
    for size in range(len(parts), 0, -1):
        candidate = "/".join(parts[:size])
        if candidate in index:
            return index[candidate]
    return None


def _file_id(path: str) -> str:
    return PurePosixPath(path).as_posix()
