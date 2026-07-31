"""Pydantic schemas for the runtime analysis API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.runtime.model import RuntimeStatus


class RuntimeStartRequest(BaseModel):
    """Request body for starting a runtime execution run."""

    project_id: str = Field(min_length=1)


class TestStartRequest(BaseModel):
    """Request body for starting a test execution run."""

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


class TestCaseSchema(BaseModel):
    """Serializable outcome of one executed test case."""

    name: str
    outcome: str
    duration_seconds: float = 0.0
    message: str | None = None


class TestSuiteSchema(BaseModel):
    """Serializable result of one language's test suite."""

    language: str
    tests_run: int
    passed: int
    failed: int
    skipped: int
    duration_seconds: float = 0.0
    error: str | None = None


class TestSuiteDetail(TestSuiteSchema):
    """A test suite including individual test case outcomes."""

    cases: list[TestCaseSchema] = Field(default_factory=list)


class TestSummary(BaseModel):
    """Lifecycle state of one test run."""

    id: str
    project_id: str
    status: RuntimeStatus
    created_at: datetime
    updated_at: datetime
    error: str | None = None


class TestDetail(TestSummary):
    """A test run including aggregate outcome summaries."""

    languages: list[str] = Field(default_factory=list)
    tests_run: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    succeeded: bool = False


class ReplayStepSchema(BaseModel):
    """One navigable position in the replay timeline."""

    index: int
    event: TraceEventSchema
    position: int
    total: int
    stack_depth: int
    previous_index: int | None = None
    next_index: int | None = None


class ReplaySummarySchema(BaseModel):
    """Overview of a language's replay timeline."""

    language: str
    total_events: int = 0
    count_by_type: dict[str, int] = Field(default_factory=dict)
    function_order: list[str] = Field(default_factory=list)
    exception: RuntimeExceptionSchema | None = None
    max_stack_depth: int = 0
    first_index: int | None = None
    last_index: int | None = None


class ReplayStepListSchema(BaseModel):
    """A filtered, paginated slice of the replay timeline."""

    language: str
    total: int = 0
    offset: int = 0
    limit: int = 0
    items: list[ReplayStepSchema] = Field(default_factory=list)
