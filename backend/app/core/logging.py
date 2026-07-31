"""Structured logging for XDebug.

Every subsystem emits one JSON object per log record so output can be ingested
by tools such as Loki or Elasticsearch without ad-hoc parsing. The envelope is::

    {
        "timestamp": "2026-07-31T12:00:00.000+00:00",
        "level": "INFO",
        "logger": "xdebug.http",
        "message": "request completed",
        "context": {"request_id": "..."},
        "status": 200
    }

A custom :class:`StructuredLogger` provides a ``structured()`` method that
attaches arbitrary keyword fields to a record without the attribute-collision
restrictions of the stdlib ``extra`` parameter (``module``, ``message``,
``level`` and friends are reserved on ``LogRecord``).
"""

from __future__ import annotations

import contextvars
import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any, cast

_RESERVED_KEYS = {"timestamp", "level", "logger", "message", "exception", "context"}


class StructuredLogger(logging.Logger):
    """Standard logger with safe structured-field support."""

    def structured(self, level: int, msg: str, *args: Any, **fields: Any) -> None:
        """Emit a record with arbitrary ``fields`` attached to the JSON output."""
        if not self.isEnabledFor(level):
            return
        frame = sys._getframe(1)
        fn = frame.f_code.co_filename
        lno = frame.f_lineno
        func = frame.f_code.co_name
        record = self.makeRecord(self.name, level, fn, lno, msg, args, None, func, None)
        if fields:
            cast(Any, record)._xdebug_extra = dict(fields)
        self.handle(record)


logging.setLoggerClass(StructuredLogger)

_log_context: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "xdebug_log_context", default=None
)


class JsonFormatter(logging.Formatter):
    """Serialize log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        """Render one log record as a JSON object string."""
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        context = _log_context.get()
        if context:
            payload["context"] = dict(context)

        extras = getattr(record, "_xdebug_extra", None)
        if extras:
            for key, value in extras.items():
                if key in _RESERVED_KEYS:
                    continue
                payload[key] = value

        return json.dumps(payload, default=str)


def configure_logging(level: str | int = "INFO") -> None:
    """Configure the root logger to emit JSON records to stdout."""
    root = logging.getLogger()
    root.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.handlers = [handler]
    root.propagate = False

    if isinstance(level, str) and level.upper() == "DEBUG":
        return
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> StructuredLogger:
    """Return a structured logger bound to ``name`` (typically ``__name__``)."""
    logger = logging.getLogger(name)
    return cast(StructuredLogger, logger)


class log_context:
    """Temporarily attach context fields to every log record.

    Usage::

        with log_context(request_id="abc", module="analysis"):
            logger.info("parsing started")

    The fields are emitted under the ``context`` key and automatically removed
    when the block exits.
    """

    def __init__(self, **fields: Any) -> None:
        self._fields = fields
        self._token: contextvars.Token[dict[str, Any] | None] | None = None

    def __enter__(self) -> log_context:
        """Merge the new fields into the ambient log context."""
        merged = {**(_log_context.get() or {}), **self._fields}
        self._token = _log_context.set(merged)
        return self

    def __exit__(self, *exc: Any) -> None:
        """Restore the previous context state."""
        if self._token is not None:
            _log_context.reset(self._token)
