"""Tests for structured JSON logging."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.core.logging import JsonFormatter, get_logger, log_context


def _capture(
    logger: logging.Logger, formatter: JsonFormatter
) -> tuple[list[dict[str, Any]], logging.Handler]:
    """Attach a capturing handler to ``logger`` and return records plus handler."""
    records: list[dict[str, Any]] = []

    class CaptureHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(json.loads(formatter.format(record)))

    handler = CaptureHandler()
    logger.addHandler(handler)
    return records, handler


def test_json_formatter_produces_valid_envelope() -> None:
    """Every record serializes to the documented JSON shape."""
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="app.mod",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )
    payload = json.loads(formatter.format(record))
    assert payload["level"] == "INFO"
    assert payload["logger"] == "app.mod"
    assert payload["message"] == "hello world"
    assert "timestamp" in payload


def test_log_context_attaches_fields_only_inside_block() -> None:
    """Context fields appear on records within the block and vanish outside."""
    logger = get_logger("xdebug.test")
    records, handler = _capture(logger, JsonFormatter())
    try:
        with log_context(request_id="abc-123"):
            logger.info("inside context")
        logger.info("outside context")
    finally:
        logger.removeHandler(handler)

    assert records[0]["context"]["request_id"] == "abc-123"
    assert "context" not in records[1]


def test_structured_fields_are_attached() -> None:
    """Fields passed to ``structured`` are emitted as top-level JSON keys."""
    logger = get_logger("xdebug.test")
    records, handler = _capture(logger, JsonFormatter())
    try:
        logger.structured(logging.INFO, "done", duration_ms=12.5, status=200)
    finally:
        logger.removeHandler(handler)

    assert records[0]["duration_ms"] == 12.5
    assert records[0]["status"] == 200


def test_structured_fields_cannot_overwrite_reserved_keys() -> None:
    """Structured fields may not corrupt the envelope's reserved fields."""
    logger = get_logger("xdebug.test")
    records, handler = _capture(logger, JsonFormatter())
    try:
        logger.structured(
            logging.INFO,
            "message",
            message="hijack",
            logger="evil",
            timestamp="fake",
        )
    finally:
        logger.removeHandler(handler)

    assert records[0]["message"] == "message"
    assert records[0]["logger"] == "xdebug.test"
    assert records[0]["timestamp"] != "fake"
