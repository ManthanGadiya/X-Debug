"""Static analysis pipeline service.

Orchestrates the Phase 3 analysis stages for a loaded project:

1. Read each source file from disk.
2. Parse it into the canonical AST model (per language).
3. Build the dependency graph.
4. Build the call graph.
5. Build the control flow graph.
6. Build the data flow graph.

The result is a deterministic :class:`AnalysisResult` containing every graph
plus the parsed modules. Per the architecture, partial results are preferred
over total failure: a file that fails to parse is logged and skipped rather
than aborting the analysis.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from app.analysis.callgraph import CallGraphBuilder
from app.analysis.cfg import CFGBuilder
from app.analysis.dataflow import DataFlowAnalyzer
from app.analysis.dependency import DependencyGraphBuilder
from app.analysis.graph import Graph
from app.analysis.model import ModuleAST
from app.analysis.parsers import default_registry
from app.analysis.parsers.base import ParserRegistry
from app.core.errors import AnalysisError
from app.core.logging import StructuredLogger, get_logger
from app.projects.loader import Project

logger = get_logger(__name__)


@dataclass
class AnalysisResult:
    """Complete static analysis output for one project."""

    project_id: str
    modules: list[ModuleAST] = field(default_factory=list)
    unparsed_files: list[str] = field(default_factory=list)
    dependency_graph: Graph | None = None
    call_graph: Graph | None = None
    cfg: Graph | None = None
    dataflow_graph: Graph | None = None

    @property
    def parsed_file_count(self) -> int:
        """Return the number of successfully parsed source files."""
        return len(self.modules)

    @property
    def failed_file_count(self) -> int:
        """Return the number of source files that could not be parsed."""
        return len(self.unparsed_files)


class AnalysisService:
    """Run the static analysis pipeline for a loaded project."""

    def __init__(
        self,
        parser_registry: ParserRegistry | None = None,
        *,
        logger: StructuredLogger = logger,
    ) -> None:
        self._parser_registry = parser_registry or default_registry()
        self._logger = logger
        self._dependency = DependencyGraphBuilder()
        self._callgraph = CallGraphBuilder()
        self._cfg = CFGBuilder()
        self._dataflow = DataFlowAnalyzer()

    def analyze(self, project: Project) -> AnalysisResult:
        """Analyze ``project`` and return the complete static analysis result."""
        root = Path(project.root_path)
        sources = _read_sources(root, project)

        modules: list[ModuleAST] = []
        unparsed: list[str] = []
        for path in project.source_files:
            if path.language is None:
                continue
            parser = self._parser_registry.get(path.language)
            if parser is None:
                unparsed.append(path.path)
                continue
            try:
                module = parser.parse(sources[path.path], path.path)
                modules.append(module)
            except SyntaxError as exc:
                unparsed.append(path.path)
                self._logger.structured(
                    logging.WARNING,
                    "module failed to parse",
                    file=path.path,
                    reason=str(exc),
                    project_id=project.id,
                )

        result = AnalysisResult(project_id=project.id, modules=modules, unparsed_files=unparsed)

        if modules:
            result.dependency_graph = self._dependency.build(modules)
            result.call_graph = self._callgraph.build(modules)
            result.cfg = self._cfg.build(modules, sources)
            result.dataflow_graph = self._dataflow.build(modules, sources)

        self._logger.structured(
            logging.INFO,
            "static analysis complete",
            project_id=project.id,
            modules=len(modules),
            unparsed=len(unparsed),
        )
        return result


def _read_sources(root: Path, project: Project) -> dict[str, str]:
    sources: dict[str, str] = {}
    for file in project.files:
        path = root / file.path
        try:
            sources[file.path] = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            raise AnalysisError(
                reason="Failed to read source file",
                module="Analysis Service",
                detail={"file": file.path, "error": str(exc)},
            ) from exc
    return sources
