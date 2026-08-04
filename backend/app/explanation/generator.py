"""Deterministic explanation generator.

Converts a :class:`LocalizationResult` plus the artifacts that produced it
into a structured :class:`ExplanationReport`. No model is involved: every
section is derived from recorded analysis output, so running the same inputs
twice produces identical reports (docs/XAI_METHEDOLOGY.md §4, §15).
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.analysis.graph import Graph, GraphNode
from app.explanation.model import (
    EvidenceReference,
    ExplanationReport,
    ExplanationStatus,
    WhereReference,
)
from app.localization.model import EvidenceSource, LocalizationResult
from app.runtime.model import RuntimeResult

_ARTIFACT_NAMES: dict[EvidenceSource, str] = {
    EvidenceSource.AST: "AST Analysis",
    EvidenceSource.DEPENDENCY_GRAPH: "Dependency Graph",
    EvidenceSource.CALL_GRAPH: "Call Graph",
    EvidenceSource.CFG: "Control Flow Graph",
    EvidenceSource.DATA_FLOW: "Data Flow Analysis",
    EvidenceSource.RUNTIME_TRACE: "Runtime Trace",
    EvidenceSource.STACK_TRACE: "Stack Trace",
}


class ExplanationGenerator:
    """Build an explanation report from a localization result."""

    def generate(
        self,
        localization: LocalizationResult,
        graph: Graph | None = None,
        runtime: RuntimeResult | None = None,
        *,
        project_id: str = "",
    ) -> ExplanationReport:
        """Return the report for ``localization`` and its supporting artifacts."""
        now = datetime.now(UTC)
        root_cause = localization.root_cause
        return ExplanationReport(
            project_id=project_id,
            status=ExplanationStatus.READY,
            created_at=now,
            updated_at=now,
            resolved=localization.resolved,
            error_summary=self._error_summary(localization, runtime),
            root_cause=(
                f"{root_cause.label} ({self._location(graph, root_cause.node_id)})"
                if root_cause is not None
                else None
            ),
            why=self._why(localization),
            where=self._where(localization, graph),
            evidence=self._evidence(localization),
            suggested_fix=localization.suggested_fix,
            confidence=localization.confidence,
            propagation_path=list(localization.propagation_path),
            missing_sources=list(localization.missing_sources),
            insufficient_evidence=(
                not localization.resolved or bool(localization.missing_sources)
            ),
        )

    # -- section builders ----------------------------------------------

    def _error_summary(
        self, localization: LocalizationResult, runtime: RuntimeResult | None
    ) -> str:
        """Summarize what happened: the observed failure."""
        if runtime is not None and runtime.exception is not None:
            exc = runtime.exception
            return f"{exc.type}: {exc.message}"
        return localization.summary

    def _why(self, localization: LocalizationResult) -> str:
        """Why it happened: the causal chain from the recorded execution order."""
        path = list(localization.propagation_path)
        if localization.resolved and path:
            if len(path) == 1:
                return (
                    f"The failure originated in {path[0]}, where the recorded "
                    "stack trace and execution order agree."
                )
            end = path[-1]
            middle = ", ".join(path[1:-1]) if len(path) > 2 else ""
            if middle:
                return (
                    f"The failure originated in {path[0]}, propagated through "
                    f"{middle}, and crashed at {end}. This chain follows the "
                    "recorded stack trace and execution order."
                )
            return (
                f"The failure originated in {path[0]} and crashed at {end}. "
                "This chain follows the recorded stack trace and execution order."
            )
        if localization.resolved:
            return (
                "The recorded evidence supports a single root cause, though "
                "no propagation chain was recorded."
            )
        if localization.candidates:
            return (
                "The evidence does not clear the confidence threshold, so a "
                "single root cause cannot be asserted. The candidates below are "
                "ranked by the available evidence."
            )
        return (
            "Insufficient evidence to determine the root cause with high confidence."
        )

    def _where(
        self, localization: LocalizationResult, graph: Graph | None
    ) -> list[WhereReference]:
        """Where it happened: concrete locations from the graph."""
        refs: list[WhereReference] = []
        seen: set[tuple[str, str, int | None]] = set()

        def add(node: GraphNode | None, node_id: str, label: str) -> None:
            ref = self._reference(node, node_id, label)
            if ref is None:
                return
            key = (ref.file, ref.function, ref.line)
            if key in seen:
                return
            seen.add(key)
            refs.append(ref)

        if localization.root_cause is not None:
            add(
                self._node(graph, localization.root_cause.node_id),
                localization.root_cause.node_id,
                localization.root_cause.label,
            )
        for label in localization.propagation_path:
            add(self._node_by_label(graph, label), "", label)
        return refs

    def _evidence(self, localization: LocalizationResult) -> list[EvidenceReference]:
        """Evidence: every supporting analysis artifact, traceable by name."""
        references: list[EvidenceReference] = []
        for item in localization.evidence_summary:
            references.append(
                EvidenceReference(
                    source=item.source.value,
                    description=item.description,
                    score=item.score,
                    artifact=_ARTIFACT_NAMES.get(
                        item.source, item.source.value.replace("_", " ").title()
                    ),
                )
            )
        return references

    # -- graph helpers --------------------------------------------------

    def _node(self, graph: Graph | None, node_id: str) -> GraphNode | None:
        if graph is None:
            return None
        return graph.nodes.get(node_id)

    def _node_by_label(self, graph: Graph | None, label: str) -> GraphNode | None:
        """Return the first node whose label matches ``label``.

        Prefers a node with a recorded file location; deterministic for a given
        graph.
        """
        if graph is None or not label:
            return None
        fallback: GraphNode | None = None
        for node in graph.nodes.values():
            if node.label != label:
                continue
            if "file" in node.metadata:
                return node
            if fallback is None:
                fallback = node
        return fallback

    def _reference(
        self, node: GraphNode | None, node_id: str, label: str
    ) -> WhereReference | None:
        """Build a location reference from a node or, failing that, its id."""
        file: str | None = None
        line: int | None = None
        qualname: str = ""
        if node is not None:
            file = str(node.metadata["file"]) if "file" in node.metadata else None
            line = self._to_int(node.metadata.get("line"))
            qualname = node.label or node_id
        else:
            qualname = label or node_id
        if file is None:
            file, parsed_qualname = self._parse_node_id(node_id)
            if parsed_qualname:
                qualname = parsed_qualname
        if file is None or not file:
            return None
        cls, function = self._split_qualname(qualname)
        if not function:
            function = qualname
        return WhereReference(file=file, function=function, cls=cls, line=line)

    def _location(self, graph: Graph | None, node_id: str) -> str:
        """Return a short ``file:line`` (or id) locator for a node."""
        node = self._node(graph, node_id)
        if node is None:
            return node_id
        file = node.metadata.get("file")
        line = self._to_int(node.metadata.get("line"))
        if file and line is not None:
            return f"{file}:{line}"
        if file:
            return str(file)
        return node_id

    @staticmethod
    def _parse_node_id(node_id: str) -> tuple[str, str]:
        """Split ``path::qualname`` into (file, qualname)."""
        if "::" in node_id:
            file, _, qualname = node_id.rpartition("::")
            return file, qualname
        return node_id, ""

    @staticmethod
    def _split_qualname(qualname: str) -> tuple[str, str]:
        """Split ``Class.method`` into (class, method); bare names return ("", name)."""
        if "." in qualname:
            cls, _, method = qualname.rpartition(".")
            return cls, method
        return "", qualname

    @staticmethod
    def _to_int(value: object) -> int | None:
        """Coerce a metadata value to an int, or ``None`` if it cannot."""
        if value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value.strip())
            except ValueError:
                return None
        return None
