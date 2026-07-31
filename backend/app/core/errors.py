"""Structured errors.

Every module returns either a success value or a structured error that can be
serialized into the documented envelope (see docs/ARCHITECTURE.md §18)::

    {
        "status": "error",
        "module": "CFG Builder",
        "reason": "Syntax Error",
        "file": "main.py",
        "line": 45
    }

Analysis continues whenever possible; partial results are preferred over total
failure.
"""

from __future__ import annotations

from typing import Any


class XDebugError(Exception):
    """Base class for all XDebug errors."""

    status_code = 500
    default_reason = "Internal error"

    def __init__(
        self,
        reason: str | None = None,
        *,
        module: str | None = None,
        file: str | None = None,
        line: int | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        self.module = module
        self.file = file
        self.line = line
        self.detail = detail or {}
        super().__init__(reason or self.default_reason)

    @property
    def reason(self) -> str:
        """Return the human-readable failure message."""
        return str(self.args[0])

    def to_dict(self) -> dict[str, Any]:
        """Serialize the error into the structured envelope."""
        payload: dict[str, Any] = {"status": "error", "reason": self.reason}
        if self.module:
            payload["module"] = self.module
        if self.file:
            payload["file"] = self.file
        if self.line is not None:
            payload["line"] = self.line
        if self.detail:
            payload["detail"] = self.detail
        return payload


class ConfigError(XDebugError):
    """Raised when configuration is invalid or incomplete."""


class NotFoundError(XDebugError):
    """Raised when a requested resource does not exist."""

    status_code = 404
    default_reason = "Resource not found"


class ValidationError(XDebugError):
    """Raised when input validation fails."""

    status_code = 422
    default_reason = "Validation failed"


class AnalysisError(XDebugError):
    """Raised when an analysis stage fails.

    Per the architecture, analysis continues when possible and partial results
    are preferred over total failure.
    """
