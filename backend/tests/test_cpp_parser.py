"""Unit tests for the C++ language parser."""

from __future__ import annotations

from app.analysis.parsers.cpp import CPParser
from app.projects.languages import Language


def _parse(source: str, path: str = "main.cpp"):
    return CPParser().parse(source, path)


def test_parses_includes() -> None:
    module = _parse('#include <iostream>\n#include "greeter.h"\n')
    assert [imp.module for imp in module.imports] == ["iostream", "greeter.h"]
    assert module.language == Language.CPP


def test_parses_class_with_methods_and_bases() -> None:
    module = _parse(
        "class Child : public Base, private Other {\n"
        "public:\n"
        "    int method(int a);\n"
        "    void inline_method() { run(); }\n"
        "private:\n"
        "    int count_;\n"
        "};\n"
    )
    assert [cls.name for cls in module.classes] == ["Child"]
    cls = module.classes[0]
    assert cls.bases == ["Base", "Other"]
    assert [method.name for method in cls.methods] == ["method", "inline_method"]
    assert cls.methods[0].params == ["a"]
    assert cls.methods[1].calls == ["run"]


def test_class_data_members_are_not_methods() -> None:
    module = _parse("class Counter {\npublic:\n    int count_;\n};\n")
    assert module.classes[0].methods == []


def test_out_of_class_method_definition_is_function() -> None:
    module = _parse(
        "class Greeter {\npublic:\n    int greet(int times);\n};\n"
        "int Greeter::greet(int times) {\n    return times + 1;\n}\n"
    )
    assert module.classes[0].methods[0].name == "greet"
    assert any(fn.name == "greet" for fn in module.functions)


def test_namespace_functions_extracted() -> None:
    module = _parse("namespace util {\n" "    int add(int a, int b) { return a + b; }\n" "}\n")
    assert [fn.name for fn in module.functions] == ["add"]
    assert module.functions[0].params == ["a", "b"]


def test_call_extraction_handles_field_and_qualified() -> None:
    module = _parse(
        "void run() {\n"
        "    obj.method(1, 2);\n"
        "    free_func();\n"
        "    ns::nsfunc();\n"
        "    x->arrow();\n"
        "}\n"
    )
    calls = module.functions[0].calls
    assert "method" in calls
    assert "free_func" in calls
    assert "nsfunc" in calls
    assert "arrow" in calls
