"""Pydantic schemas for the runtime analysis API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.runtime.model import RuntimeStatus


class RuntimeStartRequest(BaseModel):
    """Request body for starting a runtime execution run."""

    project_id: str = Field(min_length=1)


class RuntimeExceptionSchema(BaseModel):
    """Serializable exception captured during execution."""

    type: str
    message: str


class RuntimeSummary(BaseModel):
    """Lifecycle state of one runtime run."""

    id: str
    project_id: str
    status: RuntimeStatus
    created_at: datetime
    updated_at: datetime
    error: str | None = None


class RuntimeDetail(RuntimeSummary):
    """A runtime run including per-language outcome summaries."""

    languages: list[str] = Field(default_factory=list)
    succeeded: bool = False


class TraceEventSchema(BaseModel):
    """Serializable execution trace event."""

    type: str
    function: str
    filename: str
    lineno: int
    timestamp: float
    depth: int
    variables: dict[str, object] = Field(default_factory=dict)
    exception: str | None = None


class RuntimeResultSchema(BaseModel):
    """Serializable runtime outcome for one language entry point."""

    language: str
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0
    exception: RuntimeExceptionSchema | None = None
    event_count: int = 0
    function_order: list[str] = Field(default_factory=list)
    error: str | None = None


class RuntimeTraceDetail(RuntimeResultSchema):
    """A runtime result including the full captured execution trace."""

    events: list[TraceEventSchema] = Field(default_factory=list)
