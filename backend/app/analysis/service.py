"""Static analysis pipeline service.

Orchestrates the Phase 3 analysis stages for a loaded project:

1. Read each source file from disk.
2. Parse it into the canonical AST model (per language), in parallel when the
   project has multiple files.
3. Build the dependency graph.
4. Build the call graph.
5. Build the control flow graph.
6. Build the data flow graph.

The result is a deterministic :class:`AnalysisResult` containing every graph
plus the parsed modules. Per the architecture, partial results are preferred
over total failure: a file that fails to parse is logged and skipped rather
than aborting the analysis.

Parsing is parallelized with a thread pool because both ``ast`` and
tree-sitter release the GIL while parsing. Only parsers marked
:attr:`Parser.thread_safe` are shared across workers; the rest get a fresh
instance per worker. Results are assembled in ``project.source_files`` order so
parallel execution stays deterministic.
"""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path

from app.analysis.callgraph import CallGraphBuilder
from app.analysis.cfg import CFGBuilder
from app.analysis.dataflow import DataFlowAnalyzer
from app.analysis.dependency import DependencyGraphBuilder
from app.analysis.graph import Graph
from app.analysis.model import ModuleAST
from app.analysis.parsers import default_registry
from app.analysis.parsers.base import ParserRegistry
from app.analysis.parsers.cache import ParseCache
from app.core.errors import AnalysisError
from app.core.logging import StructuredLogger, get_logger
from app.projects.loader import Project, SourceFileRecord

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
        cache: ParseCache | None = None,
        max_workers: int = 0,
        logger: StructuredLogger = logger,
    ) -> None:
        self._parser_registry = parser_registry or default_registry()
        self._cache = cache or ParseCache()
        self._logger = logger
        self._dependency = DependencyGraphBuilder()
        self._callgraph = CallGraphBuilder()
        self._cfg = CFGBuilder()
        self._dataflow = DataFlowAnalyzer()
        if max_workers == 0:
            max_workers = min(32, (os.cpu_count() or 1) + 4)
        self._max_workers = max_workers

    def analyze(self, project: Project) -> AnalysisResult:
        """Analyze ``project`` and return the complete static analysis result."""
        root = Path(project.root_path)
        sources = _read_sources(root, project)
        modules, unparsed = self._parse_source_files(sources, project)

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
            workers=self._max_workers,
            cache_hits=self._cache.hit_count,
            cache_misses=self._cache.miss_count,
        )
        return result

    def _parse_source_files(
        self, sources: dict[str, str], project: Project
    ) -> tuple[list[ModuleAST], list[str]]:
        """Parse every source file, preserving ``source_files`` order.

        Returns ``(modules, unparsed_paths)``. Files are parsed concurrently
        when the project has more than one file and more than one worker is
        configured; a single file is always parsed directly to keep the common
        case free of pool overhead.
        """
        tasks = [file for file in project.source_files if file.language is not None]
        if len(tasks) <= 1 or self._max_workers == 1:
            results = [self._parse_one(sources, project.id, file) for file in tasks]
        else:
            with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
                results = list(pool.map(partial(self._parse_one, sources, project.id), tasks))

        modules = [module for module, _ in results if module is not None]
        unparsed = [path for _, path in results if path is not None]
        return modules, unparsed

    def _parse_one(
        self, sources: dict[str, str], project_id: str, source_file: SourceFileRecord
    ) -> tuple[ModuleAST | None, str | None]:
        """Parse a single source file, consulting the cache first.

        Returns ``(module, None)`` on success or ``(None, path)`` when the file
        has no supported parser or fails to parse. Unsupported-language and
        parse failures are treated identically to the sequential pipeline.
        """
        if source_file.language is None:
            return None, source_file.path
        parser = self._parser_registry.get(source_file.language)
        if parser is None:
            return None, source_file.path
        source = sources[source_file.path]
        module = self._cache.get(source_file.language, source_file.path, source)
        if module is not None:
            return module, None
        if not parser.thread_safe:
            parser = type(parser)()
        try:
            module = parser.parse(source, source_file.path)
        except SyntaxError as exc:
            self._logger.structured(
                logging.WARNING,
                "module failed to parse",
                file=source_file.path,
                reason=str(exc),
                project_id=project_id,
            )
            return None, source_file.path
        self._cache.put(source_file.language, source_file.path, source, module)
        return module, None


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
