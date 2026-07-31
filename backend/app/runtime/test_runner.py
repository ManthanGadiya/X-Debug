"""Test execution runner.

Runs a project's available tests in bounded child processes and produces a
structured :class:`TestExecution` result. Python projects run through pytest
with a JUnit XML report so every test case, its outcome, and its duration is
captured deterministically. C and C++ projects have their test files compiled
and executed with the configured toolchain.
"""

from __future__ import annotations

import logging
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from app.core.logging import StructuredLogger, get_logger
from app.projects.languages import Language
from app.projects.loader import Project, SourceFileRecord
from app.runtime.model import TestCase, TestCaseOutcome, TestExecution, TestSuite
from app.runtime.runner import RuntimeRunner, _truncate

logger = get_logger(__name__)

_TEST_NAME_PREFIXES = ("test_", "tests_")
_TEST_NAME_SUFFIXES = ("_test.py", ".test.py")
_C_TEST_NAMES = ("test_main.c", "tests_main.c")


def _is_python_test(path: str) -> bool:
    name = Path(path).name.lower()
    return name.startswith(_TEST_NAME_PREFIXES) or name.endswith(_TEST_NAME_SUFFIXES)


def _is_c_test(path: str) -> bool:
    lowered = path.lower()
    if lowered in _C_TEST_NAMES:
        return True
    return "/tests/" in lowered.lower() or lowered.startswith("tests/")


class TestRunner:
    """Execute tests in child processes with enforced resource limits."""

    def __init__(
        self,
        runner: RuntimeRunner | None = None,
        *,
        timeout_seconds: int = 120,
        max_output_chars: int = 50_000,
        logger: StructuredLogger = logger,
    ) -> None:
        self._runner = runner or RuntimeRunner(
            timeout_seconds=timeout_seconds, max_output_chars=max_output_chars
        )
        self._timeout_seconds = timeout_seconds
        self._max_output_chars = max_output_chars
        self._logger = logger

    def run(self, project: Project) -> TestExecution:
        """Run every detectable test suite of ``project``."""
        root = Path(project.root_path)
        suites: dict[str, TestSuite] = {}
        python_files = [
            f
            for f in project.source_files
            if f.language == Language.PYTHON and _is_python_test(f.path)
        ]
        c_files = [
            f
            for f in project.source_files
            if f.language in (Language.C, Language.CPP) and _is_c_test(f.path)
        ]

        if python_files:
            suites[Language.PYTHON.value] = self._run_python_tests(root)
        if c_files:
            suites[Language.C.value] = self._run_compiled_tests(root, c_files)

        self._logger.structured(
            logging.INFO,
            "test execution complete",
            project_id=project.id,
            suites=list(suites),
            total_tests=sum(suite.tests_run for suite in suites.values()),
        )
        return TestExecution(project_id=project.id, suites=suites)

    def _run_python_tests(self, root: Path) -> TestSuite:
        with tempfile.TemporaryDirectory(prefix="xdebug-test-") as temp_dir:
            junit_path = Path(temp_dir) / "junit.xml"
            command = [
                str(Path(sys.executable)),
                "-m",
                "pytest",
                str(root),
                "-q",
                "--junitxml",
                str(junit_path),
                "--no-header",
            ]
            started = time.monotonic()
            _run_subprocess(command, root, self._timeout_seconds)
            duration = time.monotonic() - started
            return _parse_junit(junit_path, duration, self._max_output_chars)

    def _run_compiled_tests(self, root: Path, files: list[SourceFileRecord]) -> TestSuite:
        cases: list[TestCase] = []
        suite_duration = 0.0
        failures = 0
        for file in files:
            entry = root / file.path
            language = file.language or Language.C
            run = (
                self._runner.run_c(entry, root)
                if language == Language.C
                else self._runner.run_cpp(entry, root)
            )
            suite_duration += run.duration_seconds
            passed = run.exit_code == 0
            if not passed:
                failures += 1
            cases.append(
                TestCase(
                    name=file.path,
                    outcome=TestCaseOutcome.PASSED if passed else TestCaseOutcome.FAILED,
                    duration_seconds=run.duration_seconds,
                    message=(run.error or run.stderr[:500]) if not passed else None,
                )
            )
        return TestSuite(
            language=Language.C.value,
            tests_run=len(cases),
            passed=len(cases) - failures,
            failed=failures,
            skipped=0,
            duration_seconds=suite_duration,
            cases=cases,
        )


def _run_subprocess(
    command: list[str], workdir: Path, timeout_seconds: int
) -> subprocess.CompletedProcess[str]:
    """Run ``command`` with a wall-clock timeout, returning the outcome."""
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=str(workdir),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return subprocess.CompletedProcess(
            args=command,
            returncode=-1,
            stdout=exc.stdout if isinstance(exc.stdout, str) else "",
            stderr=exc.stderr if isinstance(exc.stderr, str) else "",
        )
    except OSError as exc:
        return subprocess.CompletedProcess(
            args=command,
            returncode=-1,
            stdout="",
            stderr=f"Failed to start process: {exc}",
        )


def _parse_junit(junit_path: Path, duration: float, max_output_chars: int) -> TestSuite:
    """Parse a JUnit XML report into a :class:`TestSuite`."""
    if not junit_path.is_file():
        return TestSuite(
            language=Language.PYTHON.value,
            tests_run=0,
            passed=0,
            failed=0,
            skipped=0,
            duration_seconds=duration,
            error="pytest did not produce a report",
        )
    try:
        tree = ET.parse(junit_path)
    except ET.ParseError as exc:
        return TestSuite(
            language=Language.PYTHON.value,
            tests_run=0,
            passed=0,
            failed=0,
            skipped=0,
            duration_seconds=duration,
            error=f"Invalid JUnit report: {exc}",
        )
    root = tree.getroot()
    cases: list[TestCase] = []
    for case in root.iter("testcase"):
        name = case.get("name", "unknown")
        case_time = float(case.get("time", "0") or 0)
        failure = case.find("failure")
        failure_error = case.find("error")
        skipped_element = case.find("skipped")
        if failure is not None:
            outcome = TestCaseOutcome.FAILED
            message = _truncate(failure.text or failure.get("message") or "", max_output_chars)
        elif failure_error is not None:
            outcome = TestCaseOutcome.ERROR
            message = _truncate(
                failure_error.text or failure_error.get("message") or "", max_output_chars
            )
        elif skipped_element is not None:
            outcome = TestCaseOutcome.SKIPPED
            message = None
        else:
            outcome = TestCaseOutcome.PASSED
            message = None
        cases.append(
            TestCase(
                name=name,
                outcome=outcome,
                duration_seconds=case_time,
                message=message,
            )
        )

    passed = sum(1 for case in cases if case.outcome == TestCaseOutcome.PASSED)
    failed_outcomes = (TestCaseOutcome.FAILED, TestCaseOutcome.ERROR)
    failed = sum(1 for case in cases if case.outcome in failed_outcomes)
    skipped_count = sum(1 for case in cases if case.outcome == TestCaseOutcome.SKIPPED)
    return TestSuite(
        language=Language.PYTHON.value,
        tests_run=len(cases),
        passed=passed,
        failed=failed,
        skipped=skipped_count,
        duration_seconds=duration,
        cases=cases,
    )
