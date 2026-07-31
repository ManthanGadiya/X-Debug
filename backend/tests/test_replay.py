"""Unit tests for the execution replay engine."""

from __future__ import annotations

from app.runtime.model import RuntimeException, TraceEvent, TraceEventType
from app.runtime.replay import ExecutionReplay


def _event(
    type_: TraceEventType,
    function: str,
    *,
    lineno: int = 1,
    exception: str | None = None,
) -> TraceEvent:
    return TraceEvent(
        type=type_,
        function=function,
        filename="main.py",
        lineno=lineno,
        timestamp=0.0,
        depth=0,
        exception=exception,
    )


def test_empty_replay_reports_no_events() -> None:
    """An empty trace exposes an empty, non-navigable timeline."""
    replay = ExecutionReplay([])

    assert replay.total_events == 0
    assert replay.count_by_type() == {}
    assert replay.function_order() == []
    assert replay.max_stack_depth() == 0
    assert replay.exception() is None
    assert replay.first_index() is None
    assert replay.last_index() is None


def test_step_out_of_range_raises() -> None:
    """Stepping outside the timeline raises IndexError."""
    replay = ExecutionReplay([_event(TraceEventType.CALL, "main")])

    try:
        replay.step(5)
    except IndexError:
        pass
    else:
        raise AssertionError("expected IndexError")


def test_step_exposes_position_and_navigation() -> None:
    """A step carries its position and links to its neighbours."""
    events = [
        _event(TraceEventType.CALL, "main"),
        _event(TraceEventType.CALL, "helper"),
        _event(TraceEventType.RETURN, "helper"),
    ]
    replay = ExecutionReplay(events)

    step = replay.step(1)
    assert step.index == 1
    assert step.position == 2
    assert step.total == 3
    assert step.previous_index == 0
    assert step.next_index == 2

    assert replay.step(0).previous_index is None
    assert replay.step(0).next_index == 1
    assert replay.step(2).previous_index == 1
    assert replay.step(2).next_index is None


def test_stack_depth_tracks_call_and_return() -> None:
    """Stack depth grows on call and shrinks on return."""
    events = [
        _event(TraceEventType.CALL, "main"),
        _event(TraceEventType.CALL, "helper"),
        _event(TraceEventType.LINE, "helper"),
        _event(TraceEventType.RETURN, "helper"),
        _event(TraceEventType.RETURN, "main"),
    ]
    replay = ExecutionReplay(events)

    depths = [replay.step(index).stack_depth for index in range(5)]
    assert depths == [0, 1, 2, 2, 1]
    assert replay.max_stack_depth() == 2


def test_stack_depth_never_goes_negative() -> None:
    """Unbalanced returns are clamped at zero."""
    events = [
        _event(TraceEventType.RETURN, "main"),
        _event(TraceEventType.LINE, "module"),
    ]
    replay = ExecutionReplay(events)

    assert [replay.step(index).stack_depth for index in range(2)] == [0, 0]
    assert replay.max_stack_depth() == 0


def test_count_by_type_groups_events() -> None:
    """Events are grouped by their type value."""
    events = [
        _event(TraceEventType.CALL, "main"),
        _event(TraceEventType.LINE, "main"),
        _event(TraceEventType.CALL, "helper"),
        _event(TraceEventType.RETURN, "helper"),
    ]
    replay = ExecutionReplay(events)

    assert replay.count_by_type() == {"call": 2, "line": 1, "return": 1}


def test_function_order_lists_call_events() -> None:
    """Function order reflects the recorded call sequence."""
    events = [
        _event(TraceEventType.CALL, "main"),
        _event(TraceEventType.LINE, "main"),
        _event(TraceEventType.CALL, "helper"),
        _event(TraceEventType.RETURN, "helper"),
    ]
    replay = ExecutionReplay(events)

    assert replay.function_order() == ["main", "helper"]


def test_exception_extracts_type_and_message() -> None:
    """The last exception event is structured into a RuntimeException."""
    events = [
        _event(TraceEventType.CALL, "main"),
        _event(TraceEventType.EXCEPTION, "main", exception="ValueError: kaboom"),
    ]
    replay = ExecutionReplay(events)

    assert replay.exception() == RuntimeException(type="ValueError", message="kaboom")


def test_exception_without_separator_keeps_message() -> None:
    """An exception string without a colon retains its full text as the type."""
    replay = ExecutionReplay([_event(TraceEventType.EXCEPTION, "main", exception="Boom")])

    assert replay.exception() == RuntimeException(type="Boom", message="Boom")


def test_exception_returns_none_without_exception_events() -> None:
    """A trace without exceptions reports none."""
    replay = ExecutionReplay([_event(TraceEventType.CALL, "main")])

    assert replay.exception() is None


def test_exception_prefers_recorded_run_exception() -> None:
    """The recorded run exception wins over trace-level exception events."""
    events = [_event(TraceEventType.EXCEPTION, "main", exception="StopIteration: ")]
    replay = ExecutionReplay(
        events, exception=RuntimeException(type="ValueError", message="kaboom")
    )

    assert replay.exception() == RuntimeException(type="ValueError", message="kaboom")


def test_steps_filters_by_event_type() -> None:
    """Steps can be filtered to a single event type."""
    events = [
        _event(TraceEventType.CALL, "main"),
        _event(TraceEventType.LINE, "main"),
        _event(TraceEventType.RETURN, "main"),
    ]
    replay = ExecutionReplay(events)

    total, steps = replay.steps(event_type="line")
    assert total == 1
    assert steps[0].index == 1


def test_steps_filters_by_function_substring() -> None:
    """Steps can be filtered by a function name substring."""
    events = [
        _event(TraceEventType.CALL, "alpha"),
        _event(TraceEventType.CALL, "beta"),
        _event(TraceEventType.CALL, "alphabet"),
    ]
    replay = ExecutionReplay(events)

    total, steps = replay.steps(function="alpha")
    assert total == 2
    assert [step.event.function for step in steps] == ["alpha", "alphabet"]


def test_steps_combines_filters() -> None:
    """Event type and function filters combine."""
    events = [
        _event(TraceEventType.CALL, "main"),
        _event(TraceEventType.LINE, "main"),
        _event(TraceEventType.CALL, "helper"),
    ]
    replay = ExecutionReplay(events)

    total, steps = replay.steps(event_type="call", function="main")
    assert total == 1
    assert steps[0].event.function == "main"


def test_steps_paginates_with_offset_and_limit() -> None:
    """Pagination slices the filtered timeline deterministically."""
    events = [_event(TraceEventType.CALL, f"f{index}") for index in range(10)]
    replay = ExecutionReplay(events)

    total, steps = replay.steps(offset=2, limit=3)
    assert total == 10
    assert [step.index for step in steps] == [2, 3, 4]


def test_steps_rejects_negative_offset() -> None:
    """Negative pagination values raise ValueError."""
    replay = ExecutionReplay([_event(TraceEventType.CALL, "main")])

    try:
        replay.steps(offset=-1)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")
