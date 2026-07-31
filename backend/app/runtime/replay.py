"""Execution replay.

Reconstructs the captured execution timeline into a deterministic, navigable
playback view. Replay never re-executes the program; it operates purely on the
trace events recorded by :mod:`app.runtime.harness`, so the same run can be
stepped through repeatedly with identical results.

Each event in the timeline is exposed as a :class:`ReplayStep` carrying its
position, a reconstructed call-stack depth, and links to the neighbouring steps
so a client can walk forwards and backwards like a debugger.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.runtime.model import RuntimeException, TraceEvent, TraceEventType


@dataclass
class ReplayStep:
    """One navigable position in the replay timeline."""

    index: int
    event: TraceEvent
    position: int
    total: int
    stack_depth: int
    previous_index: int | None = None
    next_index: int | None = None


def _compute_stack_depths(events: list[TraceEvent]) -> list[int]:
    """Return the reconstructed call-stack depth of every event."""
    depths: list[int] = []
    stack = 0
    for event in events:
        if event.type == TraceEventType.CALL:
            depths.append(stack)
            stack += 1
        elif event.type == TraceEventType.RETURN:
            depths.append(stack)
            stack = max(0, stack - 1)
        else:
            depths.append(stack)
    return depths


class ExecutionReplay:
    """Deterministic playback view over a captured execution trace."""

    def __init__(self, events: list[TraceEvent], exception: RuntimeException | None = None) -> None:
        self._events = list(events)
        self._exception = exception
        self._stack_depths = _compute_stack_depths(self._events)

    @property
    def total_events(self) -> int:
        """Return the number of events in the timeline."""
        return len(self._events)

    def count_by_type(self) -> dict[str, int]:
        """Return event counts grouped by :class:`TraceEventType` value."""
        counts: dict[str, int] = {}
        for event in self._events:
            counts[event.type.value] = counts.get(event.type.value, 0) + 1
        return counts

    def function_order(self) -> list[str]:
        """Return functions in the order their calls were recorded."""
        return [event.function for event in self._events if event.type == TraceEventType.CALL]

    def max_stack_depth(self) -> int:
        """Return the deepest call-stack nesting observed during replay."""
        return max(self._stack_depths, default=0)

    def exception_event(self) -> TraceEvent | None:
        """Return the last captured exception event, if any."""
        for event in reversed(self._events):
            if event.type == TraceEventType.EXCEPTION:
                return event
        return None

    def exception(self) -> RuntimeException | None:
        """Return the run's authoritative exception, falling back to the trace.

        The trace may contain exception events raised by the harness itself
        while formatting the original failure, so the recorded run exception is
        preferred when available.
        """
        if self._exception is not None:
            return self._exception
        event = self.exception_event()
        if event is None or event.exception is None:
            return None
        type_name, separator, message = event.exception.partition(": ")
        return RuntimeException(type=type_name, message=message if separator else event.exception)

    def first_index(self) -> int | None:
        """Return the index of the first event, or None for an empty timeline."""
        return 0 if self._events else None

    def last_index(self) -> int | None:
        """Return the index of the last event, or None for an empty timeline."""
        return len(self._events) - 1 if self._events else None

    def step(self, index: int) -> ReplayStep:
        """Return the step at ``index`` with navigation links."""
        if index < 0 or index >= len(self._events):
            raise IndexError(f"replay step index out of range: {index}")
        return ReplayStep(
            index=index,
            event=self._events[index],
            position=index + 1,
            total=len(self._events),
            stack_depth=self._stack_depths[index],
            previous_index=index - 1 if index > 0 else None,
            next_index=index + 1 if index + 1 < len(self._events) else None,
        )

    def steps(
        self,
        *,
        event_type: str | None = None,
        function: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[int, list[ReplayStep]]:
        """Return a filtered, paginated slice of the timeline."""
        if offset < 0 or limit < 0:
            raise ValueError("offset and limit must be non-negative")
        matched = [
            step
            for step in (self.step(index) for index in range(len(self._events)))
            if (event_type is None or step.event.type.value == event_type)
            and (function is None or function in step.event.function)
        ]
        return len(matched), matched[offset : offset + limit]
