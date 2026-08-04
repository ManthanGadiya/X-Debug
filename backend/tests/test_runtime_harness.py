"""Tests for the Python runtime trace harness."""

from __future__ import annotations

import json
import os
import runpy
import sys
from pathlib import Path
from types import SimpleNamespace

import app.runtime.harness as harness_module
import pytest
from app.runtime.harness import (
    TraceCollector,
    _is_within,
    _run_target,
    _safe,
    _short_path,
    _snapshot,
    _trim_harness_frames,
    main,
)


class _StubFrame:
    def __init__(self) -> None:
        self.f_code = SimpleNamespace(co_name="stub", co_filename="stub.py")
        self.f_lineno = 10
        self.f_locals = {"x": 1}


def test_short_path_trims_long_paths() -> None:
    """Long paths are trimmed to the maximum length."""
    long_path = "x" * 500
    assert _short_path(long_path) == long_path[-300:]


def test_short_path_keeps_short_paths() -> None:
    """Short paths are returned unchanged."""
    assert _short_path("main.py") == "main.py"


def test_safe_keeps_primitives() -> None:
    """Primitive values pass through the snapshot safely."""
    assert _safe(None) is None
    assert _safe(42) == 42
    assert _safe("text") == "text"
    assert _safe(True) is True


def test_safe_bounds_collections() -> None:
    """Collections are bounded to the snapshot limit."""
    assert _safe(list(range(100))) == list(range(25))
    snapshot = _safe({"a": 1, "b": [1, 2, 3]})
    assert snapshot["a"] == 1
    assert snapshot["b"] == [1, 2, 3]


def test_safe_reprs_objects() -> None:
    """Objects are reduced to their string representation."""
    snapshot = _safe(object())
    assert isinstance(snapshot, str)


def test_snapshot_captures_locals() -> None:
    """A frame's locals are captured into a snapshot dict."""
    import inspect

    frame = inspect.currentframe()
    assert frame is not None
    snapshot = _snapshot(frame)
    assert isinstance(snapshot, dict)


def test_collector_serializes_empty() -> None:
    """An empty collector serializes an empty event list."""
    collector = TraceCollector()
    payload = collector.to_json()
    assert '"events": []' in payload


def test_collector_call_event_records_variables() -> None:
    """A call event records function, location, and variables."""
    collector = TraceCollector()
    trace = collector.trace_function
    frame = _StubFrame()
    result = trace(frame, "call", None)

    assert callable(result)
    assert len(collector.events) == 1
    event = collector.events[0]
    assert event.type.value == "call"
    assert event.function == "stub"
    assert event.filename == "stub.py"
    assert event.lineno == 10
    assert event.variables == {"x": 1}


def test_collector_return_and_line_events() -> None:
    """Return and line events are recorded in order."""
    collector = TraceCollector()
    trace = collector.trace_function
    frame = _StubFrame()

    assert trace(frame, "return", None) is None
    assert callable(trace(frame, "line", None))
    assert callable(trace(frame, "opcode", None))

    types = [event.type.value for event in collector.events]
    assert types == ["return", "line"]


def test_collector_exception_event_records_last_exception() -> None:
    """An exception event records the last raised exception."""
    collector = TraceCollector()
    trace = collector.trace_function
    frame = _StubFrame()
    arg = (ValueError, ValueError("kaboom"), None)

    assert callable(trace(frame, "exception", arg))

    assert collector.events[-1].exception == "ValueError: kaboom"
    payload = collector.to_json()
    assert '"type": "ValueError"' in payload
    assert '"message": "kaboom"' in payload


def test_collector_skips_generated_filenames() -> None:
    """Events from generated filenames are skipped."""
    collector = TraceCollector()
    trace = collector.trace_function
    frame = _StubFrame()
    frame.f_code = SimpleNamespace(co_name="gen", co_filename="<generated>")

    assert callable(trace(frame, "call", None))
    assert collector.events == []


def test_run_target_writes_trace_file(tmp_path) -> None:
    """Running a target writes a trace file on success."""
    source = tmp_path / "ok.py"
    source.write_text("def f():\n    return 1\n\nprint(f())\n", encoding="utf-8")
    trace_path = tmp_path / "trace.json"
    os.environ["XDEBUG_TRACE_OUTPUT"] = str(trace_path)
    try:
        assert _run_target(source, []) == 0
    finally:
        os.environ.pop("XDEBUG_TRACE_OUTPUT", None)

    assert trace_path.is_file()
    payload = json.loads(trace_path.read_text(encoding="utf-8"))
    assert len(payload["events"]) > 0


def test_run_target_writes_trace_on_failure(tmp_path) -> None:
    """Running a failing target still writes a trace file."""
    source = tmp_path / "fail.py"
    source.write_text("raise RuntimeError('bad')\n", encoding="utf-8")
    trace_path = tmp_path / "trace.json"
    os.environ["XDEBUG_TRACE_OUTPUT"] = str(trace_path)
    try:
        assert _run_target(source, []) == 1
    finally:
        os.environ.pop("XDEBUG_TRACE_OUTPUT", None)

    payload = json.loads(trace_path.read_text(encoding="utf-8"))
    assert payload["last_exception"] is not None
    assert payload["last_exception"]["type"] == "RuntimeError"


def test_run_target_restores_previous_trace_function(tmp_path) -> None:
    """The ambient trace function survives a target run (e.g. coverage)."""
    source = tmp_path / "ok.py"
    source.write_text("x = 1\n", encoding="utf-8")
    prev = sys.gettrace()
    try:
        assert _run_target(source, []) == 0
        assert sys.gettrace() is prev
    finally:
        sys.settrace(prev)


def test_is_within_matches_root_nested_and_sibling(tmp_path: Path) -> None:
    """Path containment handles equal, nested, and sibling paths."""
    root = tmp_path / "repo"
    inside = tmp_path / "repo" / "sub" / "main.py"
    outside = tmp_path / "other" / "file.py"
    prefix_trap = tmp_path / "repo-other" / "file.py"
    assert _is_within(str(inside), str(root))
    assert _is_within(str(root), str(root))
    assert not _is_within(str(outside), str(root))
    assert not _is_within(str(prefix_trap), str(root))


def test_collector_skips_empty_filename() -> None:
    """Events without a filename are skipped."""
    collector = TraceCollector()
    frame = _StubFrame()
    frame.f_code = SimpleNamespace(co_name="anon", co_filename="")
    assert callable(collector.trace_function(frame, "call", None))
    assert collector.events == []


def test_collector_filters_events_outside_root(tmp_path: Path) -> None:
    """Events outside the configured root are skipped."""
    outside = tmp_path.parent / "outside" / "file.py"
    collector = TraceCollector(str(tmp_path))
    frame = _StubFrame()
    frame.f_code = SimpleNamespace(co_name="outside", co_filename=str(outside))
    assert callable(collector.trace_function(frame, "call", None))
    assert collector.events == []


def test_run_target_prints_trace_without_harness_frames(tmp_path, capsys) -> None:
    """The failure traceback omits frames owned by the harness."""
    source = tmp_path / "boom.py"
    source.write_text("raise RuntimeError('boom')\n", encoding="utf-8")
    assert _run_target(source, []) == 1
    captured = capsys.readouterr()
    assert "RuntimeError" in captured.err
    assert "boom.py" in captured.err
    assert "harness.py" not in captured.err


def test_run_target_invalid_syntax_returns_1(tmp_path) -> None:
    """Invalid target source is reported as a failed run (exit 1)."""
    source = tmp_path / "bad.py"
    source.write_text("def broken(:\n", encoding="utf-8")
    assert _run_target(source, []) == 1


def test_trim_harness_frames_drops_matching_frames(monkeypatch) -> None:
    """Frames matching the harness file are removed from a traceback."""

    def raise_error() -> None:
        raise RuntimeError("boom")

    try:
        raise_error()
    except RuntimeError as exc:
        tb = exc.__traceback__
        original_head = tb.tb_frame.f_code.co_filename
        monkeypatch.setattr(harness_module, "__file__", original_head)
        trimmed = _trim_harness_frames(tb)

    assert trimmed is None


def test_main_missing_target_returns_2(tmp_path, monkeypatch, capsys) -> None:
    """The CLI reports a missing target on stderr with exit code 2."""
    missing = tmp_path / "does-not-exist.py"
    monkeypatch.setattr(sys, "argv", ["harness", str(missing)])
    assert main() == 2
    assert "target not found" in capsys.readouterr().err


def test_main_runs_valid_target(tmp_path, monkeypatch) -> None:
    """The CLI executes a valid target successfully."""
    source = tmp_path / "ok.py"
    source.write_text("print('hi')\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["harness", str(source)])
    assert main() == 0


def test_main_without_target_exits_2(monkeypatch) -> None:
    """Missing required CLI arguments exit with code 2."""
    monkeypatch.setattr(sys, "argv", ["harness"])
    with pytest.raises(SystemExit) as excinfo:
        main()
    assert excinfo.value.code == 2


def test_module_main_guard_exits_2(monkeypatch) -> None:
    """Executing the module as __main__ routes through the CLI."""
    monkeypatch.setattr(sys, "argv", ["harness"])
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_path(str(Path(harness_module.__file__)), run_name="__main__")
    assert excinfo.value.code == 2
