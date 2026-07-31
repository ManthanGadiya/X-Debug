"""Parser factory."""

from __future__ import annotations

from app.analysis.parsers.base import Parser as Parser
from app.analysis.parsers.base import ParserRegistry as ParserRegistry
from app.analysis.parsers.c import CParser as CParser
from app.analysis.parsers.cpp import CPParser as CPParser
from app.analysis.parsers.python import PythonParser as PythonParser


def default_registry() -> ParserRegistry:
    """Return a registry with every supported language parser registered."""
    registry = ParserRegistry()
    registry.register(PythonParser())
    registry.register(CParser())
    registry.register(CPParser())
    return registry
