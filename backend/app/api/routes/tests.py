"""Test execution endpoints.

POST /tests/run                — start an asynchronous test run for a project
GET  /tests/{run_id}           — retrieve the lifecycle state and result summary
GET  /tests/{run_id}/results/{language} — retrieve per-language test results
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, Path, status

from app.container import ContainerDep
from app.runtime.model import TestSuite
from app.runtime.test_manager import TestManager, TestRun
from app.runtime.test_runner import TestRunner
from app.schemas.projects import ProjectStartRequest
from app.schemas.runtime import (
    TestCaseSchema,
    TestDetail,
    TestSuiteDetail,
    TestSummary,
)

router = APIRouter(prefix="/tests", tags=["tests"])


@router.get(
    "",
    response_model=list[TestSummary],
    summary="List test runs",
)
def list_test_runs(container: ContainerDep) -> list[TestSummary]:
    """Return all test execution runs, most recent first."""
    return [_to_summary(record) for record in container.test_manager.list()]


@router.post(
    "/run",
    response_model=TestSummary,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start a test execution run",
)
def start_test_run(
    container: ContainerDep,
    request: ProjectStartRequest,
    background_tasks: BackgroundTasks,
) -> TestSummary:
    """Queue a test execution run for a previously ingested project."""
    project = container.repository_manager.get_project(request.project_id)
    record = container.test_manager.start(project.id)

    manager: TestManager = container.test_manager
    runner: TestRunner = container.test_runner
    background_tasks.add_task(manager.run, record.id, lambda: runner.run(project))
    return _to_summary(record)


@router.get(
    "/{run_id}",
    response_model=TestDetail,
    summary="Retrieve test run state and result summary",
)
def get_test_run(run_id: str, container: ContainerDep) -> TestDetail:
    """Return the lifecycle state of a test run."""
    record = container.test_manager.get(run_id)
    return _to_detail(record)


@router.get(
    "/{run_id}/results/{language}",
    response_model=TestSuiteDetail,
    summary="Retrieve per-language test results",
)
def get_test_results(
    run_id: str,
    container: ContainerDep,
    language: str = Path(..., pattern="^(Python|C|C\\+\\+)$"),
) -> TestSuiteDetail:
    """Return the test results captured for ``language`` in a finished run."""
    record = container.test_manager.get(run_id)
    if record.status.value != "ready" or record.result is None:
        raise HTTPException(
            status_code=409,
            detail=f"Test run is not ready (status={record.status.value})",
        )
    suite = record.result.suites.get(language)
    if suite is None:
        raise HTTPException(status_code=404, detail=f"No test results for language {language}")
    return _to_suite_detail(suite)


def _to_summary(record: TestRun) -> TestSummary:
    return TestSummary(
        id=record.id,
        project_id=record.project_id,
        status=record.status,
        created_at=record.created_at,
        updated_at=record.updated_at,
        error=record.error,
    )


def _to_detail(record: TestRun) -> TestDetail:
    result = record.result
    return TestDetail(
        id=record.id,
        project_id=record.project_id,
        status=record.status,
        created_at=record.created_at,
        updated_at=record.updated_at,
        error=record.error,
        languages=list(result.suites) if result else [],
        tests_run=result.total_tests_run if result else 0,
        passed=sum(suite.passed for suite in result.suites.values()) if result else 0,
        failed=sum(suite.failed for suite in result.suites.values()) if result else 0,
        skipped=sum(suite.skipped for suite in result.suites.values()) if result else 0,
        succeeded=result.succeeded if result else False,
    )


def _to_suite_detail(suite: TestSuite) -> TestSuiteDetail:
    return TestSuiteDetail(
        language=suite.language,
        tests_run=suite.tests_run,
        passed=suite.passed,
        failed=suite.failed,
        skipped=suite.skipped,
        duration_seconds=suite.duration_seconds,
        error=suite.error,
        cases=[
            TestCaseSchema(
                name=case.name,
                outcome=case.outcome.value,
                duration_seconds=case.duration_seconds,
                message=case.message,
            )
            for case in suite.cases
        ],
    )
