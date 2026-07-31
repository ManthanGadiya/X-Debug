"""Subprocess execution runner with resource limits.

Executes analyzed code in a child process so that a misbehaving target cannot
crash the backend. Every execution is bounded by:

* a hard wall-clock timeout
* a maximum captured output size
* a maximum number of trace events

Python targets run through the :mod:`app.runtime.harness` tracer so their
execution timeline is captured. C and C++ targets are compiled with the
configured compiler before being executed.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from app.core.logging import StructuredLogger, get_logger
from app.runtime.model import (
    RuntimeException,
    RuntimeResult,
    RuntimeStatus,
    TraceEvent,
    TraceEventType,
)

logger = get_logger(__name__)

_COMPILER_HINTS: list[Path] = [
    Path(r"C:\Program Files\JetBrains\CLion 2026.2\bin\mingw\bin"),
    Path(r"C:\MinGW\bin"),
    Path(r"C:\msys64\mingw64\bin"),
]


@dataclass
class _Completed:
    """Bounded outcome of a subprocess run."""

    returncode: int
    stdout: str
    stderr: str
    duration_seconds: float


def _resolve_tool(name: str) -> str | None:
    """Locate an executable on PATH or in known toolchain directories."""
    found = shutil.which(name)
    if found:
        return found
    for directory in _COMPILER_HINTS:
        candidate = directory / f"{name}.exe"
        if candidate.is_file():
            return str(candidate)
    return None


def _truncate(text: str, limit: int) -> str:
    """Bound captured output to ``limit`` characters."""
    if len(text) <= limit:
        return text
    return text[:limit] + "\n... [truncated]"


class RuntimeRunner:
    """Execute targets in child processes with enforced resource limits."""

    def __init__(
        self,
        *,
        timeout_seconds: int = 60,
        max_output_chars: int = 50_000,
        max_trace_events: int = 10_000,
        logger: StructuredLogger = logger,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._max_output_chars = max_output_chars
        self._max_trace_events = max_trace_events
        self._logger = logger
        self._python_path = str(Path(sys.executable))
        self._harness_path = str(Path(__file__).with_name("harness.py"))

    def run_python(self, entry: Path, workdir: Path) -> RuntimeResult:
        """Execute a Python entry point under tracing with resource limits."""
        with tempfile.TemporaryDirectory(prefix="xdebug-trace-") as temp_dir:
            trace_path = Path(temp_dir) / "trace.json"
            env = self._child_env()
            env["XDEBUG_TRACE_OUTPUT"] = str(trace_path)
            command = [self._python_path, self._harness_path, str(entry)]
            completed = self._run_command(command, env=env, workdir=workdir)
            exception, events = _read_trace(trace_path, self._max_trace_events)
            return RuntimeResult(
                status=RuntimeStatus.READY,
                exit_code=completed.returncode,
                stdout=_truncate(completed.stdout, self._max_output_chars),
                stderr=_truncate(completed.stderr, self._max_output_chars),
                duration_seconds=completed.duration_seconds,
                exception=exception,
                events=events,
            )

    def run_c(self, entry: Path, workdir: Path) -> RuntimeResult:
        """Compile and execute a C entry point with resource limits."""
        return self._run_compiled(entry, workdir, language="c")

    def run_cpp(self, entry: Path, workdir: Path) -> RuntimeResult:
        """Compile and execute a C++ entry point with resource limits."""
        return self._run_compiled(entry, workdir, language="cpp")

    def _run_compiled(self, entry: Path, workdir: Path, *, language: str) -> RuntimeResult:
        tool_name = "gcc" if language == "c" else "g++"
        tool = _resolve_tool(tool_name)
        if tool is None:
            return RuntimeResult(
                status=RuntimeStatus.FAILED,
                error=f"Compiler not found: {tool_name}",
            )
        standard = "-std=c11" if language == "c" else "-std=c++17"
        with tempfile.TemporaryDirectory(prefix="xdebug-build-") as temp_dir:
            binary = Path(temp_dir) / "program.exe"
            compile_result = self._run_command(
                [tool, str(entry), "-o", str(binary), standard],
                env=None,
                workdir=workdir,
            )
            if compile_result.returncode != 0:
                return RuntimeResult(
                    status=RuntimeStatus.FAILED,
                    exit_code=compile_result.returncode,
                    stderr=_truncate(compile_result.stderr, self._max_output_chars),
                    error="Compilation failed",
                )
            run_result = self._run_command([str(binary)], env=None, workdir=workdir)
            return RuntimeResult(
                status=RuntimeStatus.READY,
                exit_code=run_result.returncode,
                stdout=_truncate(run_result.stdout, self._max_output_chars),
                stderr=_truncate(run_result.stderr, self._max_output_chars),
                duration_seconds=run_result.duration_seconds,
            )

    def _run_command(
        self,
        command: list[str],
        *,
        env: dict[str, str] | None,
        workdir: Path,
    ) -> _Completed:
        started = time.monotonic()
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self._timeout_seconds,
                env=env,
                cwd=str(workdir),
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            self._logger.structured(
                logging.WARNING,
                "target execution timed out",
                command=command[0],
                timeout_seconds=self._timeout_seconds,
            )
            return _Completed(
                returncode=-1,
                stdout=exc.stdout if isinstance(exc.stdout, str) else "",
                stderr=exc.stderr if isinstance(exc.stderr, str) else "",
                duration_seconds=time.monotonic() - started,
            )
        except OSError as exc:
            self._logger.structured(
                logging.ERROR,
                "failed to start target process",
                command=command[0],
                error=str(exc),
            )
            return _Completed(
                returncode=-1,
                stdout="",
                stderr=f"Failed to start process: {exc}",
                duration_seconds=time.monotonic() - started,
            )
        return _Completed(
            returncode=completed.returncode,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
            duration_seconds=time.monotonic() - started,
        )

    def _child_env(self) -> dict[str, str]:
        """Build the child environment with the backend ``app`` package importable."""
        env = dict(os.environ)
        backend_dir = str(Path(__file__).resolve().parents[1])
        python_path = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = backend_dir + (os.pathsep + python_path if python_path else "")
        env["PYTHONUNBUFFERED"] = "1"
        return env


def _read_trace(
    trace_path: Path, max_events: int
) -> tuple[RuntimeException | None, list[TraceEvent]]:
    """Load the trace file written by the harness into model objects."""
    if not trace_path.is_file():
        return None, []
    try:
        payload = json.loads(trace_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, []
    events: list[TraceEvent] = []
    for raw in payload.get("events", [])[:max_events]:
        try:
            events.append(
                TraceEvent(
                    type=TraceEventType(raw["type"]),
                    function=raw["function"],
                    filename=raw["filename"],
                    lineno=int(raw["lineno"]),
                    timestamp=float(raw["timestamp"]),
                    depth=int(raw["depth"]),
                    variables=raw.get("variables", {}),
                    exception=raw.get("exception"),
                )
            )
        except (KeyError, ValueError):
            continue
    exception_payload = payload.get("last_exception")
    exception = (
        RuntimeException(
            type=exception_payload["type"],
            message=exception_payload["message"],
        )
        if exception_payload
        else None
    )
    return exception, events
