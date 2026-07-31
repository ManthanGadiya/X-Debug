"""Unit tests for the Python parser."""

from __future__ import annotations

from app.analysis.parsers.python import PythonParser
from app.projects.languages import Language


def _parse(source: str, path: str = "main.py"):
    return PythonParser().parse(source, path)


def test_parses_imports() -> None:
    module = _parse(
        "import os\nfrom collections import defaultdict, OrderedDict\nfrom pkg import mod as m\n"
    )
    assert [(record.module, record.names) for record in module.imports] == [
        ("os", ["os"]),
        ("collections", ["defaultdict", "OrderedDict"]),
        ("pkg", ["m"]),
    ]


def test_parses_functions_with_params_and_calls() -> None:
    module = _parse(
        "def greet(name, greeting='hi'):\n"
        "    return format(greeting, name)\n"
        "def main():\n"
        "    greet('world')\n"
    )
    assert [function.name for function in module.functions] == ["greet", "main"]
    assert module.functions[0].params == ["name", "greeting"]
    assert module.functions[0].calls == ["format"]
    assert module.functions[1].calls == ["greet"]


def test_parses_classes_with_bases_and_methods() -> None:
    module = _parse(
        "class Animal(Base, Mixin):\n"
        "    def speak(self):\n"
        "        return '...'\n"
        "    def move(self, dx, dy):\n"
        "        pass\n"
    )
    (cls,) = module.classes
    assert cls.name == "Animal"
    assert cls.bases == ["Base", "Mixin"]
    assert [method.name for method in cls.methods] == ["speak", "move"]
    assert cls.methods[0].qualname == "Animal.speak"
    assert cls.methods[1].params == ["self", "dx", "dy"]


def test_parses_variables() -> None:
    module = _parse("x = 1\ny, z = (2, 3)\nclass C:\n    value = 5\n")
    assert [(record.name, record.scope) for record in module.variables] == [
        ("x", "module"),
        ("y", "module"),
        ("z", "module"),
    ]


def test_all_functions_includes_methods() -> None:
    module = _parse(
        "def top():\n    pass\n" "class C:\n" "    def method(self):\n" "        pass\n"
    )
    assert [function.qualname for function in module.all_functions] == [
        "top",
        "C.method",
    ]


def test_parses_decorators() -> None:
    module = _parse("@app.route('/')\ndef index():\n    pass\n")
    (function,) = module.functions
    assert function.decorators == ["app.route"]


def test_parses_async_functions() -> None:
    module = _parse("async def fetch():\n    return await get()\n")
    (function,) = module.functions
    assert function.name == "fetch"
    assert function.calls == ["get"]


def test_language_is_python() -> None:
    module = _parse("pass\n")
    assert module.language == Language.PYTHON
    assert module.path == "main.py"


def test_invalid_syntax_raises() -> None:
    import pytest

    with pytest.raises(SyntaxError):
        _parse("def broken(:\n")
