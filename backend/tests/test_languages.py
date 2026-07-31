"""Unit tests for language detection."""

from __future__ import annotations

from app.projects.languages import Language, detect_language


def test_python_extensions() -> None:
    """Python source and stub files map to Python."""
    assert detect_language("main.py") == Language.PYTHON
    assert detect_language("types.pyi") == Language.PYTHON


def test_c_extensions() -> None:
    """C source and header files map to C."""
    assert detect_language("kernel.c") == Language.C
    assert detect_language("header.h") == Language.C


def test_cpp_extensions() -> None:
    """C++ source and header files map to C++."""
    assert detect_language("main.cpp") == Language.CPP
    assert detect_language("main.cc") == Language.CPP
    assert detect_language("main.cxx") == Language.CPP
    assert detect_language("header.hpp") == Language.CPP
    assert detect_language("header.hh") == Language.CPP
    assert detect_language("header.hxx") == Language.CPP


def test_unsupported_extension() -> None:
    """Unknown extensions return None."""
    assert detect_language("README.md") is None
    assert detect_language("data.json") is None


def test_detection_is_case_insensitive() -> None:
    """Extension matching ignores case."""
    assert detect_language("MAIN.PY") == Language.PYTHON
    assert detect_language("Main.CPP") == Language.CPP


def test_detection_requires_suffix_match() -> None:
    """The extension must be the file suffix, not merely present."""
    assert detect_language("notpython") is None
    assert detect_language("script.py.bak") is None
