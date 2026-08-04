"""Programming language detection for repository ingestion.

Language detection is deterministic: it maps file extensions to languages with
a fixed table. No heuristics, no confidence scores, no guesswork. Every result
can be explained by pointing at the extension-to-language rule that produced it.
"""

from __future__ import annotations

from enum import StrEnum

_EXTENSION_LANGUAGES: dict[str, str] = {
    ".py": "Python",
    ".pyi": "Python",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".hpp": "C++",
    ".hh": "C++",
    ".hxx": "C++",
}


class Language(StrEnum):
    """Languages supported by the Version 1 pipeline."""

    PYTHON = "Python"
    C = "C"
    CPP = "C++"


def detect_language(filename: str) -> Language | None:
    """Return the language for ``filename`` or ``None`` when unsupported."""
    normalized = filename.rstrip().lower()
    for suffix in _SUFFIXES_SORTED:
        if normalized.endswith(suffix):
            language = _EXTENSION_LANGUAGES[suffix]
            return Language(language)
    return None


def resolve_language(name: str) -> Language | None:
    """Return the canonical language matching ``name`` (case-insensitive).

    Language values are canonical display strings ("Python", "C", "C++"), so
    client-supplied names such as "python" or "PYTHON" are normalized to the
    value used as the runtime result key and the knowledge graph node id
    namespace.
    """
    lowered = name.strip().lower()
    for language in Language:
        if language.value.lower() == lowered:
            return language
    return None


_SUFFIXES_SORTED = sorted(_EXTENSION_LANGUAGES, key=len, reverse=True)
