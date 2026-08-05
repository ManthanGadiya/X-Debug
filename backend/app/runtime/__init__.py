"""Runtime analysis subsystem (Phase 4).

Executes project entry points in bounded child processes and captures what
actually happens during execution: exceptions, stack traces, variable values,
function execution order, and execution timestamps.
"""

from app.runtime.manager import RuntimeManager as RuntimeManager

__all__ = ["RuntimeManager"]
