"""Tests for the runtime analyzer service and entry-point detection."""

from __future__ import annotations

from pathlib import Path

from app.projects.languages import Language
from app.projects.loader import Project, ProjectLoader, SourceFileRecord
from app.runtime.runner import RuntimeRunner
from app.runtime.service import (
    RuntimeAnalyzer,
    _compiled_entry,
    _defines_main,
    _detect_entry_points,
    _python_entry,
)


def _make_project(tmp_path: Path, files: dict[str, str]) -> Project:
    root = tmp_path / "repo"
    root.mkdir(parents=True, exist_ok=True)
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    loader = ProjectLoader(max_size_bytes=1024 * 1024)
    return loader.load(root, project_id="p1", name="proj", source="test")


def test_python_entry_prefers_main(tmp_path: Path) -> None:
    """Python entry detection prefers a main.py file."""
    files = [SourceFileRecord(path="main.py", language=Language.PYTHON, size_bytes=1, lines=1)]
    entry = _python_entry(files, tmp_path)
    assert entry is not None
    assert entry.name == "main.py"


def test_python_entry_prefers_priority_names(tmp_path: Path) -> None:
    """Priority entry names win over other Python files."""
    files = [
        SourceFileRecord(path="app.py", language=Language.PYTHON, size_bytes=1, lines=1),
        SourceFileRecord(path="main.py", language=Language.PYTHON, size_bytes=1, lines=1),
    ]
    entry = _python_entry(files, tmp_path)
    assert entry is not None
    assert entry.name == "main.py"


def test_python_entry_falls_back_to_single(tmp_path: Path) -> None:
    """A lone Python file becomes the entry point."""
    files = [SourceFileRecord(path="script.py", language=Language.PYTHON, size_bytes=1, lines=1)]
    entry = _python_entry(files, tmp_path)
    assert entry is not None
    assert entry.name == "script.py"


def test_python_entry_none_for_multiple_without_convention(tmp_path: Path) -> None:
    """Multiple files without a naming convention yield no entry."""
    files = [
        SourceFileRecord(path="a.py", language=Language.PYTHON, size_bytes=1, lines=1),
        SourceFileRecord(path="b.py", language=Language.PYTHON, size_bytes=1, lines=1),
    ]
    assert _python_entry(files, tmp_path) is None


def test_compiled_entry_prefers_main_file(tmp_path: Path) -> None:
    """Compiled entry detection prefers a main file."""
    files = [
        SourceFileRecord(path="main.c", language=Language.C, size_bytes=1, lines=1),
        SourceFileRecord(path="util.c", language=Language.C, size_bytes=1, lines=1),
    ]
    entry = _compiled_entry(files, tmp_path)
    assert entry is not None
    assert entry.name == "main.c"


def test_compiled_entry_finds_main_definition(tmp_path: Path) -> None:
    """Compiled entry detection finds a file defining main."""
    main_path = tmp_path / "program.c"
    main_path.write_text("int main(void) { return 0; }\n", encoding="utf-8")
    files = [SourceFileRecord(path="program.c", language=Language.C, size_bytes=1, lines=1)]
    entry = _compiled_entry(files, tmp_path)
    assert entry is not None
    assert entry.name == "program.c"


def test_defines_main_detects_variants(tmp_path: Path) -> None:
    """Main-definition detection handles C signature variants."""
    path = tmp_path / "a.c"
    path.write_text("void main() {}\n", encoding="utf-8")
    assert _defines_main(path)
    path.write_text("int helper() { return 1; }\n", encoding="utf-8")
    assert not _defines_main(path)


def test_detect_entry_points_orders_by_language(tmp_path: Path) -> None:
    """Entry points are ordered by language priority."""
    project = _make_project(
        tmp_path,
        {
            "main.py": "print('py')\n",
            "main.c": "int main(void) { return 0; }\n",
        },
    )
    entries = _detect_entry_points(project)
    languages = [language for language, _ in entries]
    assert languages == [Language.PYTHON, Language.C]


def test_analyze_python_project_captures_runtime(tmp_path: Path) -> None:
    """Analyzing a Python project captures runtime evidence."""
    project = _make_project(
        tmp_path,
        {
            "main.py": ("def login(user):\n" "    return user\n" "\n" "print(login('alice'))\n"),
        },
    )
    analyzer = RuntimeAnalyzer(runner=RuntimeRunner(timeout_seconds=15))
    result = analyzer.analyze(project)

    assert result.project_id == "p1"
    assert result.executed_count == 1
    python_result = result.results[Language.PYTHON.value]
    assert python_result.succeeded
    assert python_result.stdout.strip() == "alice"
    assert "login" in python_result.function_order


def test_analyze_c_project_when_toolchain_available(tmp_path: Path) -> None:
    """Analyzing a C project captures output when a toolchain exists."""
    project = _make_project(
        tmp_path,
        {"main.c": '#include <stdio.h>\nint main(void) {\n    printf("ok");\n    return 0;\n}\n'},
    )
    analyzer = RuntimeAnalyzer(runner=RuntimeRunner(timeout_seconds=30))
    result = analyzer.analyze(project)

    c_result = result.results[Language.C.value]
    if c_result.error and "Compiler not found" in c_result.error:
        return
    assert c_result.succeeded
    assert c_result.stdout.strip() == "ok"
