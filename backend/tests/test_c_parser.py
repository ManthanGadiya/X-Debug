"""Unit tests for the C language parser."""

from __future__ import annotations

from app.analysis.parsers.c import CParser
from app.projects.languages import Language


def _parse(source: str, path: str = "main.c"):
    return CParser().parse(source, path)


def test_parses_includes() -> None:
    module = _parse('#include <stdio.h>\n#include "mylib.h"\n')
    assert [imp.module for imp in module.imports] == ["stdio.h", "mylib.h"]
    assert [imp.line for imp in module.imports] == [1, 2]
    assert module.language == Language.C
    assert module.path == "main.c"


def test_parses_functions_with_params_and_calls() -> None:
    module = _parse(
        "int add(int a, int b) {\n"
        "    return a + b;\n"
        "}\n"
        "int main(void) {\n"
        "    int result = add(1, 2);\n"
        "    return result;\n"
        "}\n"
    )
    assert [fn.name for fn in module.functions] == ["add", "main"]
    add = module.functions[0]
    assert add.params == ["a", "b"]
    assert add.line == 1
    assert add.calls == []
    assert module.functions[1].calls == ["add"]


def test_parses_global_variables() -> None:
    module = _parse("static int global_var = 5;\nint counter;\n")
    assert [var.name for var in module.variables] == ["global_var", "counter"]
    assert all(var.scope == "module" for var in module.variables)


def test_does_not_record_function_prototypes_as_variables() -> None:
    module = _parse("int helper(int x);\nint global = 1;\n")
    assert [var.name for var in module.variables] == ["global"]


def test_parses_struct_as_class() -> None:
    module = _parse("typedef struct Point { int x; int y; } Point;\n")
    assert [cls.name for cls in module.classes] == ["Point"]


def test_parses_anonymous_struct_ignored() -> None:
    module = _parse("struct { int x; } instance;\n")
    assert module.classes == []
    assert [var.name for var in module.variables] == ["instance"]


def test_function_call_through_pointer() -> None:
    module = _parse("void run(void) {\n    callback();\n    obj->method(1);\n}\n")
    assert "callback" in module.functions[0].calls
    assert "method" in module.functions[0].calls
