"""Runtime analysis endpoints.

POST /runtime/run         — start an asynchronous runtime execution for a project
GET  /runtime/{run_id}    — retrieve the lifecycle state and result summary
GET  /runtime/{run_id}/trace/{language} — retrieve the execution trace for one language
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, Path, status

from app.container import ContainerDep
from app.runtime import RuntimeManager
from app.runtime.manager import RuntimeRun, RuntimeStatus
from app.runtime.model import RuntimeException, RuntimeResult
from app.runtime.service import RuntimeAnalyzer
from app.schemas.runtime import (
    RuntimeDetail,
    RuntimeExceptionSchema,
    RuntimeStartRequest,
    RuntimeSummary,
    RuntimeTraceDetail,
    TraceEventSchema,
)

router = APIRouter(prefix="/runtime", tags=["runtime"])


@router.post(
    "/run",
    response_model=RuntimeSummary,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start a runtime execution run",
)
def start_run(
    container: ContainerDep,
    request: RuntimeStartRequest,
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
