"""Static analysis data model.

The model is the canonical, language-independent representation of source code
produced by the parser layer. Every parser (Python, future C/C++) emits the same
model so downstream analyses (dependency, call graph, CFG, data flow) never touch
language-specific details.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.projects.languages import Language


@dataclass
class ImportRecord:
    """A single import statement extracted from a module."""

    module: str
    names: list[str] = field(default_factory=list)
    line: int = 0


@dataclass
class FunctionDef:
    """A function or method definition."""

    name: str
    qualname: str
    params: list[str] = field(default_factory=list)
    line: int = 0
    calls: list[str] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)


@dataclass
class ClassDef:
    """A class definition with its methods and inheritance bases."""

    name: str
    qualname: str
    bases: list[str] = field(default_factory=list)
    methods: list[FunctionDef] = field(default_factory=list)
    line: int = 0


@dataclass
class VariableRecord:
    """A variable assignment/definition at module or function scope."""

    name: str
    line: int = 0
    scope: str = "module"


@dataclass
class ModuleAST:
    """Parsed representation of a single source file."""

    path: str
    language: Language
    imports: list[ImportRecord] = field(default_factory=list)
    functions: list[FunctionDef] = field(default_factory=list)
    classes: list[ClassDef] = field(default_factory=list)
    variables: list[VariableRecord] = field(default_factory=list)

    @property
    def all_functions(self) -> list[FunctionDef]:
        """Return top-level functions plus all class methods."""
        methods = [method for cls in self.classes for method in cls.methods]
        return self.functions + methods
