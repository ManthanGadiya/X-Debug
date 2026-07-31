"""Call graph construction.

Builds the function-level call graph. Nodes are functions/methods (qualified by
file and class), edges are ``calls`` relationships.

Resolution is static and deterministic, in this order:

1. The bare call name matches a function or method declared in the same module.
2. A ``self.X`` call inside a method resolves to ``X`` on that method's class.
3. The call name uniquely matches one function across the whole project.
4. Otherwise the target is recorded as an external (library/builtin) call.
"""

from __future__ import annotations

from collections import defaultdict

from app.analysis.graph import Graph, GraphNode
from app.analysis.model import FunctionDef, ModuleAST


class CallGraphBuilder:
    """Build the call graph for a set of parsed modules."""

    def build(self, modules: list[ModuleAST]) -> Graph:
        """Return the call graph for ``modules``."""
        graph = Graph(name="call")

        index = _build_index(modules)
        for module in modules:
            for function in module.all_functions:
                caller = _function_id(module.path, function.qualname)
                graph.add_node(
                    GraphNode(
                        id=caller,
                        kind="function",
                        label=function.qualname,
                        metadata={"file": module.path, "line": function.line},
                    )
                )
                for call in function.calls:
                    callee = _resolve_call(module, function, call, index)
                    if callee is not None:
                        graph.add_node(
                            GraphNode(
                                id=callee,
                                kind="function",
                                label=_label_from_id(callee),
                            )
                        )
                        graph.add_edge(caller, callee, "calls")
                    else:
                        external = _external_id(call)
                        graph.add_node(GraphNode(id=external, kind="external", label=call))
                        graph.add_edge(caller, external, "calls")

        return graph


def _build_index(modules: list[ModuleAST]) -> dict[tuple[str, str], list[str]]:
    """Map ``(module_path, simple_name)`` to every matching function id."""
    index: dict[tuple[str, str], list[str]] = defaultdict(list)
    for module in modules:
        for function in module.all_functions:
            index[(module.path, function.name)].append(_function_id(module.path, function.qualname))
    return index


def _resolve_call(
    module: ModuleAST,
    function: FunctionDef,
    call: str,
    index: dict[tuple[str, str], list[str]],
) -> str | None:
    if call.startswith("self."):
        attr = call[len("self.") :]
        class_name = function.qualname.split(".")[0]
        candidates = index.get((module.path, attr), [])
        qualified = [c for c in candidates if c.endswith(f".{class_name}.{attr}")]
        if len(qualified) == 1:
            return qualified[0]
        if len(candidates) == 1:
            return candidates[0]

    same_module = index.get((module.path, call), [])
    if len(same_module) == 1:
        return same_module[0]

    project_wide = [fid for (path, name), fids in index.items() if name == call for fid in fids]
    unique = [fid for fid in project_wide if not fid.startswith(f"{module.path}::")]
    if len(unique) == 1:
        return unique[0]
    return None


def _function_id(path: str, qualname: str) -> str:
    return f"{path}::{qualname}"


def _external_id(name: str) -> str:
    return f"external::{name}"


def _label_from_id(function_id: str) -> str:
    return function_id.split("::", 1)[1]
