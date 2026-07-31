"""Tests for the bounded subprocess runtime runner."""

from __future__ import annotations

from pathlib import Path

from app.runtime.model import RuntimeStatus, TraceEventType
from app.runtime.runner import RuntimeRunner, _read_trace, _truncate


def test_truncate_shortens_over_limit() -> None:
    """Over-limit text is truncated and marked."""
    assert _truncate("x" * 100, 10).startswith("x" * 10)
    assert "truncated" in _truncate("x" * 100, 10)


def test_truncate_keeps_under_limit() -> None:
    """Under-limit text is returned unchanged."""
    assert _truncate("short", 100) == "short"


def test_read_trace_missing_file_returns_empty(tmp_path: Path) -> None:
    """A missing trace file yields an empty result."""
    exception, events = _read_trace(tmp_path / "missing.json", 1000)
    assert exception is None
    assert events == []


def test_read_trace_skips_bad_events(tmp_path: Path) -> None:
    """Malformed events are skipped when reading a trace."""
    trace_path = tmp_path / "trace.json"
    trace_path.write_text(
        '{"events": [{"type": "call"}, {"type": "call", "function": "f",'
        ' "filename": "a.py", "lineno": 1, "timestamp": 0.0, "depth": 0}]}',
        encoding="utf-8",
    )
    exception, events = _read_trace(trace_path, 1000)
    assert exception is None
    assert len(events) == 1
    assert events[0].type == TraceEventType.CALL
    assert events[0].function == "f"


def test_run_python_captures_success_trace(tmp_path: Path) -> None:
    """Running a Python target captures a success trace."""
    entry = tmp_path / "main.py"
    entry.write_text("def add(a, b):\n    return a + b\n\nprint(add(2, 3))\n", encoding="utf-8")
    runner = RuntimeRunner(timeout_seconds=15)
    result = runner.run_python(entry, tmp_path)

    assert result.status == RuntimeStatus.READY
    assert result.exit_code == 0
    assert result.stdout.strip() == "5"
    assert result.exception is None
    assert result.event_count > 0
    types = {event.type for event in result.events}
    assert TraceEventType.CALL in types
    assert TraceEventType.RETURN in types
    assert "add" in result.function_order


def test_run_python_captures_exception(tmp_path: Path) -> None:
    """Running a crashing target captures the raised exception."""
    entry = tmp_path / "crash.py"
    entry.write_text("def boom():\n    raise ValueError('kaboom')\n\nboom()\n", encoding="utf-8")
    runner = RuntimeRunner(timeout_seconds=15)
    result = runner.run_python(entry, tmp_path)

    assert result.status == RuntimeStatus.READY
    assert result.exit_code == 1
    assert result.exception is not None
    assert result.exception.type == "ValueError"
    assert "kaboom" in result.exception.message


def test_run_python_missing_target_returns_failure(tmp_path: Path) -> None:
    """A missing Python target returns a non-zero result."""
    runner = RuntimeRunner(timeout_seconds=15)
    result = runner.run_python(tmp_path / "nope.py", tmp_path)

    assert result.status == RuntimeStatus.READY
    assert result.exit_code != 0
    assert result.exception is None
    assert result.event_count == 0


def test_run_c_compiles_and_executes_when_toolchain_available(tmp_path: Path) -> None:
    """A C target compiles and runs when a toolchain is available."""
    entry = tmp_path / "main.c"
    source = '#include <stdio.h>\nint main(void) {\n    printf("hi c");\n    return 0;\n}\n'
    entry.write_text(source, encoding="utf-8")
    runner = RuntimeRunner(timeout_seconds=30)
    result = runner.run_c(entry, tmp_path)

    if result.status == RuntimeStatus.FAILED and result.error:
        assert "Compiler not found" in result.error
        return
    assert result.status == RuntimeStatus.READY
    assert result.exit_code == 0
    assert result.stdout.strip() == "hi c"
