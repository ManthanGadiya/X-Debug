"""Generic directed graph structure.

Every graph builder (dependency, call graph, CFG, data flow) emits nodes and
edges through this shared model. Nodes carry a stable identifier and kind; edges
carry a typed relationship label. Downstream consumers can serialize or traverse
any graph without knowing which builder produced it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class GraphNode:
    """A node in a directed graph."""

    id: str
    kind: str
    label: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    """A directed edge between two graph nodes."""

    source: str
    target: str
    kind: str


@dataclass
class Graph:
    """A directed graph with unique nodes and typed edges."""

    name: str
    nodes: dict[str, GraphNode] = field(default_factory=dict)
    edges: list[GraphEdge] = field(default_factory=list)

    def add_node(self, node: GraphNode) -> None:
        """Add ``node`` if an equivalent id is not already present."""
        self.nodes.setdefault(node.id, node)

    def add_edge(self, source: str, target: str, kind: str) -> None:
        """Add a typed edge, skipping duplicates of the same source/target/kind."""
        edge = GraphEdge(source=source, target=target, kind=kind)
        if edge not in self.edges:
            self.edges.append(edge)

    @property
    def node_count(self) -> int:
        """Return the number of nodes."""
        return len(self.nodes)

    @property
    def edge_count(self) -> int:
        """Return the number of edges."""
        return len(self.edges)
