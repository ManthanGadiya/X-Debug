"""Runtime analysis endpoints.

POST /runtime/run         — start an asynchronous runtime execution for a project
GET  /runtime/{run_id}    — retrieve the lifecycle state and result summary
GET  /runtime/{run_id}/trace/{language} — retrieve the execution trace for one language
GET  /runtime/{run_id}/replay/{language} — overview of a language's replay timeline
GET  /runtime/{run_id}/replay/{language}/step — navigate to one replay step
GET  /runtime/{run_id}/replay/{language}/steps — filtered, paginated replay steps
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, Path, Query, status

from app.container import ContainerDep
from app.runtime import RuntimeManager
from app.runtime.manager import RuntimeRun, RuntimeStatus
from app.runtime.model import RuntimeException, RuntimeResult
from app.runtime.replay import ExecutionReplay, ReplayStep
from app.runtime.service import RuntimeAnalyzer
from app.schemas.projects import ProjectStartRequest
from app.schemas.runtime import (
    ReplayStepListSchema,
    ReplayStepSchema,
    ReplaySummarySchema,
    RuntimeDetail,
    RuntimeExceptionSchema,
    RuntimeSummary,
    RuntimeTraceDetail,
    TraceEventSchema,
)

router = APIRouter(prefix="/runtime", tags=["runtime"])


@router.get(
    "",
    response_model=list[RuntimeSummary],
    summary="List runtime runs",
)
def list_runtime_runs(container: ContainerDep) -> list[RuntimeSummary]:
    """Return all runtime execution runs, most recent first."""
    return [_to_summary(record) for record in container.runtime_manager.list()]


@router.post(
    "/run",
    response_model=RuntimeSummary,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start a runtime execution run",
)
def start_run(
    container: ContainerDep,
    request: ProjectStartRequest,
    background_tasks: BackgroundTasks,
) -> RuntimeSummary:
    """Queue a runtime execution run for a previously ingested project."""
    project = container.repository_manager.get_project(request.project_id)
    record = container.runtime_manager.start(project.id)

    manager: RuntimeManager = container.runtime_manager
    analyzer: RuntimeAnalyzer = container.runtime_analyzer
    background_tasks.add_task(manager.run, record.id, lambda: analyzer.analyze(project))
    return _to_summary(record)


@router.get(
    "/{run_id}",
    response_model=RuntimeDetail,
    summary="Retrieve runtime run state and result summary",
)
def get_run(run_id: str, container: ContainerDep) -> RuntimeDetail:
    """Return the lifecycle state of a runtime run."""
    record = container.runtime_manager.get(run_id)
    return _to_detail(record)


@router.get(
    "/{run_id}/trace/{language}",
    response_model=RuntimeTraceDetail,
    summary="Retrieve the execution trace for one language",
)
def get_trace(
    run_id: str,
    container: ContainerDep,
    language: str = Path(..., pattern="^(Python|C|C\\+\\+)$"),
) -> RuntimeTraceDetail:
    """Return the execution trace captured for ``language`` in a finished run."""
    record = container.runtime_manager.get(run_id)
    if record.status != RuntimeStatus.READY or record.result is None:
        raise HTTPException(
            status_code=409,
            detail=f"Runtime run is not ready (status={record.status.value})",
        )
    result = record.result.results.get(language)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No runtime result for language {language}")
    return _to_trace_detail(language, result)


@router.get(
    "/{run_id}/replay/{language}",
    response_model=ReplaySummarySchema,
    summary="Overview of a language's replay timeline",
)
def get_replay(
    run_id: str,
    container: ContainerDep,
    language: str = Path(..., pattern="^(Python|C|C\\+\\+)$"),
) -> ReplaySummarySchema:
    """Return a summary of the recorded timeline for ``language``."""
    replay = _replay_for(container, run_id, language)
    return ReplaySummarySchema(
        language=language,
        total_events=replay.total_events,
        count_by_type=replay.count_by_type(),
        function_order=replay.function_order(),
        exception=_to_exception(replay.exception()),
        max_stack_depth=replay.max_stack_depth(),
        first_index=replay.first_index(),
        last_index=replay.last_index(),
    )


@router.get(
    "/{run_id}/replay/{language}/step",
    response_model=ReplayStepSchema,
    summary="Navigate to one replay step",
)
def get_replay_step(
    run_id: str,
    container: ContainerDep,
    language: str = Path(..., pattern="^(Python|C|C\\+\\+)$"),
    index: int = Query(0, ge=0, description="Zero-based step index to navigate to"),
) -> ReplayStepSchema:
    """Return the replay step at ``index`` with its navigation links."""
    replay = _replay_for(container, run_id, language)
    try:
        step = replay.step(index)
    except IndexError:
        raise HTTPException(status_code=404, detail=f"No replay step at index {index}") from None
    return _to_step(step)


@router.get(
    "/{run_id}/replay/{language}/steps",
    response_model=ReplayStepListSchema,
    summary="Filter and paginate replay steps",
)
def get_replay_steps(
    run_id: str,
    container: ContainerDep,
    language: str = Path(..., pattern="^(Python|C|C\\+\\+)$"),
    event_type: str | None = Query(
        None,
        description="Only steps of this event type (call, return, line, exception)",
    ),
    function: str | None = Query(
        None, description="Only steps whose function name contains this value"
    ),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
) -> ReplayStepListSchema:
    """Return a filtered, paginated slice of the replay timeline."""
    replay = _replay_for(container, run_id, language)
    total, steps = replay.steps(
        event_type=event_type,
        function=function,
        offset=offset,
        limit=limit,
    )
    return ReplayStepListSchema(
        language=language,
        total=total,
        offset=offset,
        limit=len(steps),
        items=[_to_step(step) for step in steps],
    )


def _replay_for(container: ContainerDep, run_id: str, language: str) -> ExecutionReplay:
    record = container.runtime_manager.get(run_id)
    if record.status != RuntimeStatus.READY or record.result is None:
        raise HTTPException(
            status_code=409,
            detail=f"Runtime run is not ready (status={record.status.value})",
        )
    result = record.result.results.get(language)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No runtime result for language {language}")
    return ExecutionReplay(result.events, exception=result.exception)


def _to_summary(record: RuntimeRun) -> RuntimeSummary:
    return RuntimeSummary(
        id=record.id,
        project_id=record.project_id,
        status=record.status,
        created_at=record.created_at,
        updated_at=record.updated_at,
        error=record.error,
    )


def _to_detail(record: RuntimeRun) -> RuntimeDetail:
    result = record.result
    return RuntimeDetail(
        id=record.id,
        project_id=record.project_id,
        status=record.status,
        created_at=record.created_at,
        updated_at=record.updated_at,
        error=record.error,
        languages=list(result.results) if result else [],
        succeeded=result.succeeded if result else False,
    )


def _to_trace_detail(language: str, result: RuntimeResult) -> RuntimeTraceDetail:
    return RuntimeTraceDetail(
        language=language,
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        duration_seconds=result.duration_seconds,
        exception=_to_exception(result.exception),
        event_count=result.event_count,
        function_order=result.function_order,
        error=result.error,
        events=[
            TraceEventSchema(
                type=event.type.value,
                function=event.function,
                filename=event.filename,
                lineno=event.lineno,
                timestamp=event.timestamp,
                depth=event.depth,
                variables=event.variables,
                exception=event.exception,
            )
            for event in result.events
        ],
    )


def _to_exception(exception: RuntimeException | None) -> RuntimeExceptionSchema | None:
    if exception is None:
        return None
    return RuntimeExceptionSchema(type=exception.type, message=exception.message)


def _to_step(step: ReplayStep) -> ReplayStepSchema:
    event = step.event
    return ReplayStepSchema(
        index=step.index,
        event=TraceEventSchema(
            type=event.type.value,
            function=event.function,
            filename=event.filename,
            lineno=event.lineno,
            timestamp=event.timestamp,
            depth=event.depth,
            variables=event.variables,
            exception=event.exception,
        ),
        position=step.position,
        total=step.total,
        stack_depth=step.stack_depth,
        previous_index=step.previous_index,
        next_index=step.next_index,
    )
