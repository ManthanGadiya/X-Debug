"""Runtime analysis data model.

Captures what actually happened during execution: the sequence of function
calls and returns, the call stack at each point, variable value snapshots,
exceptions, and a timeline of events. This is the runtime counterpart to the
static :mod:`app.analysis` model and feeds evidence aggregation in Phase 6.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class TraceEventType(StrEnum):
    """Kinds of events recorded during execution."""

    CALL = "call"
    RETURN = "return"
    LINE = "line"
    EXCEPTION = "exception"


@dataclass
class TraceEvent:
    """One observed execution event."""

    type: TraceEventType
    function: str
    filename: str
    lineno: int
    timestamp: float
    depth: int
    variables: dict[str, Any] = field(default_factory=dict)
    exception: str | None = None


@dataclass
class RuntimeException:
    """An exception observed during execution."""

    type: str
    message: str
    traceback: list[str] = field(default_factory=list)


class RuntimeStatus(StrEnum):
    """Lifecycle states of a runtime run."""

    QUEUED = "queued"
    RUNNING = "running"
    READY = "ready"
    FAILED = "failed"


@dataclass
class RuntimeResult:
    """Outcome of executing a project or program."""

    status: RuntimeStatus
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0
    exception: RuntimeException | None = None
    events: list[TraceEvent] = field(default_factory=list)
    error: str | None = None

    @property
    def event_count(self) -> int:
        """Return the number of captured trace events."""
        return len(self.events)

    @property
    def function_order(self) -> list[str]:
        """Return functions in execution order (deduplicated per call event)."""
        return [event.function for event in self.events if event.type == TraceEventType.CALL]

    @property
    def succeeded(self) -> bool:
        """Return True when the program exited without raising."""
        return self.exception is None and self.status == RuntimeStatus.READY
