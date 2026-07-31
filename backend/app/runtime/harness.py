"""Python runtime trace harness.

Executes a target script under :func:`sys.settrace` and records the events
described by :mod:`app.runtime.model` into a JSON trace file. The harness is
launched by the runtime runner in a child process so that resource limits
apply to the entire execution including the tracing overhead.

The trace function observes:

* function calls and returns
* exceptions
* line-level execution
* snapshot of local variables at call and return

All events carry a monotonic timestamp so the execution timeline can be
reconstructed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.runtime.model import TraceEvent, TraceEventType

_MAX_VARIABLES_PER_FRAME = 25
_MAX_REPR_CHARS = 200
_MAX_FILENAME_CHARS = 300


def _safe(value: Any) -> Any:
    """Convert an arbitrary Python value into a JSON-serializable snapshot."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value[:_MAX_VARIABLES_PER_FRAME]]
    if isinstance(value, dict):
        return {
            str(key): _safe(item) for key, item in list(value.items())[:_MAX_VARIABLES_PER_FRAME]
        }
    try:
        return repr(value)[:_MAX_REPR_CHARS]
    except Exception:  # pragma: no cover - repr should rarely fail
        return "<unprintable>"


def _snapshot(frame: Any) -> dict[str, Any]:
    """Capture a bounded snapshot of ``frame.f_locals``."""
    locals_dict: dict[str, Any] = {}
    for name, value in list(frame.f_locals.items())[:_MAX_VARIABLES_PER_FRAME]:
        locals_dict[name] = _safe(value)
    return locals_dict


def _short_path(path: str) -> str:
    """Trim paths so trace files stay readable and bounded."""
    return path[-_MAX_FILENAME_CHARS:]


class TraceCollector:
    """Collector installed as a trace function via :func:`sys.settrace`."""

    def __init__(self) -> None:
        self.events: list[TraceEvent] = []
        self.start_time = time.monotonic()
        self._last_exception: tuple[type[BaseException], BaseException, Any] | None = None

    def _record(self, event: TraceEventType, frame: Any, arg: Any = None) -> TraceEvent | None:
        if not frame.f_code.co_filename or frame.f_code.co_filename.startswith("<"):
            return None
        now = time.monotonic() - self.start_time
        trace_event = TraceEvent(
            type=event,
            function=frame.f_code.co_name,
            filename=_short_path(frame.f_code.co_filename),
            lineno=frame.f_lineno,
            timestamp=now,
            depth=len(self.events),
        )
        if event in (TraceEventType.CALL, TraceEventType.RETURN):
            trace_event.variables = _snapshot(frame)
        if event == TraceEventType.EXCEPTION and arg is not None:
            exc_type, exc_value, _tb = arg
            self._last_exception = arg
            trace_event.exception = f"{exc_type.__name__}: {exc_value}"
        self.events.append(trace_event)
        return trace_event

    def trace_function(self, frame: Any, event: str, arg: Any) -> Callable[..., Any] | None:
        """sys.settrace callback."""
        if event == "call":
            self._record(TraceEventType.CALL, frame)
            return self.trace_function
        if event == "return":
            self._record(TraceEventType.RETURN, frame)
            return None
        if event == "exception":
            self._record(TraceEventType.EXCEPTION, frame, arg)
            return self.trace_function
        if event == "line":
            self._record(TraceEventType.LINE, frame)
            return self.trace_function
        return self.trace_function

    def to_json(self) -> str:
        """Serialize all captured events as JSON."""
        payload = {
            "events": [event.__dict__ for event in self.events],
            "last_exception": (
                {
                    "type": self._last_exception[0].__name__,
                    "message": str(self._last_exception[1]),
                }
                if self._last_exception is not None
                else None
            ),
        }
        return json.dumps(payload, default=str)


def _run_target(target: Path, argv: list[str]) -> int:
    """Execute the target script in this process under tracing."""
    collector = TraceCollector()
    sys.settrace(collector.trace_function)
    old_argv = sys.argv
    sys.argv = [str(target), *argv]
    try:
        source = target.read_text(encoding="utf-8")
        code = compile(source, str(target), "exec")
        exec(code, {"__name__": "__main__", "__file__": str(target)})
        return 0
    except BaseException as exc:
        traceback.print_exc()
        collector._last_exception = (type(exc), exc, exc.__traceback__)
        return 1
    finally:
        sys.argv = old_argv
        sys.settrace(None)
        trace_path = os.environ.get("XDEBUG_TRACE_OUTPUT")
        if trace_path:
            Path(trace_path).write_text(collector.to_json(), encoding="utf-8")


def main() -> int:
    """CLI entry point for the harness process."""
    parser = argparse.ArgumentParser(description="Run a Python target under a trace.")
    parser.add_argument("target", help="Path to the Python script to execute")
    parser.add_argument("args", nargs="*", help="Arguments passed to the target script")
    args = parser.parse_args()
    target = Path(args.target)
    if not target.is_file():
        sys.stderr.write(f"harness: target not found: {target}\n")
        return 2
    return _run_target(target, args.args)


if __name__ == "__main__":
    sys.exit(main())
