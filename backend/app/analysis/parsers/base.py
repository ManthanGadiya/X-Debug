"""Parser abstraction.

Every supported language registers a parser that turns raw source text into the
canonical :class:`ModuleAST` model. The registry resolves a parser by
:class:`Language`, keeping downstream analysis language-agnostic and making it
straightforward to add future languages.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.analysis.model import ModuleAST
from app.projects.languages import Language


class Parser(ABC):
    """Turn raw source text into a :class:`ModuleAST`."""

    language: Language

    @abstractmethod
    def parse(self, source: str, path: str) -> ModuleAST:
        """Parse ``source`` and return its canonical representation."""
        raise NotImplementedError


class ParserRegistry:
    """Map languages to their parsers."""

    def __init__(self, parsers: dict[Language, Parser] | None = None) -> None:
        self._parsers: dict[Language, Parser] = parsers or {}

    def register(self, parser: Parser) -> None:
        """Register ``parser`` under its declared language."""
        self._parsers[parser.language] = parser

    def get(self, language: Language) -> Parser | None:
        """Return the parser for ``language`` or ``None`` if unsupported."""
        return self._parsers.get(language)
