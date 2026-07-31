"""Parser factory."""

from __future__ import annotations

from app.analysis.parsers.base import Parser as Parser
from app.analysis.parsers.base import ParserRegistry as ParserRegistry
from app.analysis.parsers.python import PythonParser as PythonParser


def default_registry() -> ParserRegistry:
    """Return a registry with every supported language parser registered."""
    registry = ParserRegistry()
    registry.register(PythonParser())
    return registry
