"""Tests for the test execution runner."""

from __future__ import annotations

from pathlib import Path

from app.projects.languages import Language
from app.projects.loader import Project, ProjectLoader
from app.runtime.model import TestCaseOutcome
from app.runtime.runner import _run_bounded
from app.runtime.test_runner import (
    TestRunner,
    _is_c_test,
    _is_python_test,
    _parse_junit,
)


def test_is_python_test_detects_conventions() -> None:
    """Python test detection matches common naming conventions."""
    assert _is_python_test("test_main.py")
    assert _is_python_test("tests_helpers.py")
    assert _is_python_test("auth/test_login.py")
    assert not _is_python_test("main.py")
    assert not _is_python_test("testdata.py")


def test_is_c_test_detects_paths() -> None:
    """C test detection matches path conventions."""
    assert _is_c_test("tests/main.c")
    assert _is_c_test("test_main.c")
    assert _is_c_test("src/tests/main.c")
    assert _is_c_test("tests_main.c")
    assert _is_c_test("tests/helpers.c")
    assert not _is_c_test("src/main.c")


def _make_project(tmp_path: Path, files: dict[str, str]) -> Project:
    root = tmp_path / "repo"
    root.mkdir(parents=True, exist_ok=True)
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    loader = ProjectLoader(max_size_bytes=1024 * 1024)
    return loader.load(root, project_id="p1", name="proj", source="test")


def test_python_tests_pass_and_report_cases(tmp_path: Path) -> None:
    """Passing Python tests are reported per case."""
    project = _make_project(
        tmp_path,
        {
            "test_sample.py": (
                "def test_add():\n    assert 1 + 1 == 2\n\n"
                "def test_sub():\n    assert 3 - 1 == 2\n"
            )
        },
    )
    runner = TestRunner(timeout_seconds=60)
    result = runner.run(project)

    suite = result.suites[Language.PYTHON.value]
    assert suite.tests_run == 2
    assert suite.passed == 2
    assert suite.failed == 0
    assert suite.succeeded
    names = {case.name for case in suite.cases}
    assert "test_add" in names
    assert "test_sub" in names


def test_python_failing_test_reported(tmp_path: Path) -> None:
    """A failing Python test is reported with its outcome."""
    project = _make_project(
        tmp_path,
        {"test_bad.py": "def test_fails():\n    assert 1 == 2\n"},
    )
    runner = TestRunner(timeout_seconds=60)
    result = runner.run(project)

    suite = result.suites[Language.PYTHON.value]
    assert suite.tests_run == 1
    assert suite.failed == 1
    assert suite.passed == 0
    assert not suite.succeeded
    assert suite.cases[0].outcome == TestCaseOutcome.FAILED


def test_python_skipped_test_reported(tmp_path: Path) -> None:
    """A skipped Python test is counted as skipped."""
    project = _make_project(
        tmp_path,
        {"test_skip.py": "import pytest\ndef test_skip():\n    pytest.skip('later')\n"},
    )
    runner = TestRunner(timeout_seconds=60)
    result = runner.run(project)

    suite = result.suites[Language.PYTHON.value]
    assert suite.skipped == 1
    assert suite.passed == 0
    assert suite.succeeded


def test_no_python_tests_returns_no_suite(tmp_path: Path) -> None:
    """A project without test files produces no suite."""
    project = _make_project(tmp_path, {"main.py": "print('hi')\n"})
    runner = TestRunner(timeout_seconds=60)
    result = runner.run(project)

    assert result.executed_count == 0


def test_c_tests_compile_and_run_when_toolchain_available(tmp_path: Path) -> None:
    """C tests compile and run when a toolchain is available."""
    project = _make_project(
        tmp_path,
        {
            "test_main.c": "#include <assert.h>\nint main(void) {\n    assert(1 == 1);\n"
            "    return 0;\n}\n"
        },
    )
    runner = TestRunner(timeout_seconds=60)
    result = runner.run(project)

    if not result.suites:
        return
    suite = result.suites[Language.C.value]
    if suite.error and "Compiler not found" in suite.error:
        return
    assert suite.tests_run == 1
    assert suite.passed == 1


def test_parse_junit_missing_report() -> None:
    """A missing JUnit report yields an error suite."""
    suite = _parse_junit(Path("nope.xml"), 1.0, 100)
    assert suite.error is not None
    assert suite.tests_run == 0


def test_parse_junit_parses_cases(tmp_path: Path) -> None:
    """JUnit cases parse into outcomes with correct counts."""
    junit = tmp_path / "junit.xml"
    junit.write_text(
        '<?xml version="1.0"?>\n<testsuite>\n'
        '  <testcase name="test_a" time="0.1"/>\n'
        '  <testcase name="test_b" time="0.2">\n'
        '    <failure message="boom">trace</failure>\n'
        "  </testcase>\n"
        '  <testcase name="test_c" time="0.3">\n'
        "    <skipped/>\n"
        "  </testcase>\n"
        "</testsuite>\n",
        encoding="utf-8",
    )
    suite = _parse_junit(junit, 1.0, 100)
    assert suite.tests_run == 3
    assert suite.passed == 1
    assert suite.failed == 1
    assert suite.skipped == 1
    outcomes = {case.name: case.outcome for case in suite.cases}
    assert outcomes["test_a"] == TestCaseOutcome.PASSED
    assert outcomes["test_b"] == TestCaseOutcome.FAILED
    assert outcomes["test_c"] == TestCaseOutcome.SKIPPED


def test_parse_junit_invalid_xml_reports_error(tmp_path: Path) -> None:
    """Malformed JUnit XML yields an error suite."""
    junit = tmp_path / "junit.xml"
    junit.write_text("<<< not xml", encoding="utf-8")
    suite = _parse_junit(junit, 1.0, 100)

    assert suite.tests_run == 0
    assert suite.error is not None
    assert "Invalid JUnit report" in suite.error


def test_parse_junit_error_element_reports_error_outcome(tmp_path: Path) -> None:
    """A JUnit error element maps to the ERROR outcome."""
    junit = tmp_path / "junit.xml"
    junit.write_text(
        '<?xml version="1.0"?>\n<testsuite>\n'
        '  <testcase name="test_err" time="0.1">\n'
        '    <error message="oops">boom</error>\n'
        "  </testcase>\n"
        "</testsuite>\n",
        encoding="utf-8",
    )
    suite = _parse_junit(junit, 1.0, 100)

    assert suite.tests_run == 1
    assert suite.failed == 1
    assert suite.cases[0].outcome == TestCaseOutcome.ERROR
    assert suite.cases[0].message is not None


def test_run_subprocess_times_out(tmp_path: Path) -> None:
    """A subprocess exceeding the timeout returns a non-zero outcome."""
    import sys

    completed = _run_bounded(
        [sys.executable, "-c", "import time; time.sleep(10)"],
        workdir=tmp_path,
        timeout_seconds=1,
    )

    assert completed.returncode == -1


def test_run_subprocess_missing_executable_reports_oserror(tmp_path: Path) -> None:
    """A missing executable returns a process start error."""
    completed = _run_bounded(
        [str(tmp_path / "missing.exe")], workdir=tmp_path, timeout_seconds=15
    )

    assert completed.returncode == -1
    assert "Failed to start process" in completed.stderr


def test_c_failing_test_reported_per_case(tmp_path: Path) -> None:
    """A failing C test is reported as a failed case."""
    project = _make_project(
        tmp_path,
        {
            "test_main.c": "#include <assert.h>\nint main(void) {\n    assert(1 == 2);\n"
            "    return 0;\n}\n"
        },
    )
    runner = TestRunner(timeout_seconds=60)
    result = runner.run(project)

    if not result.suites:
        return
    suite = result.suites[Language.C.value]
    if suite.error and "Compiler not found" in suite.error:
        return
    assert suite.tests_run == 1
    assert suite.failed == 1
    assert suite.passed == 0
    assert suite.cases[0].outcome == TestCaseOutcome.FAILED
