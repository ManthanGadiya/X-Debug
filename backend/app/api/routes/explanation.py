"""Explanation endpoints.

POST /explanation/{project_id} — generate an explanation from the stored
                          localization result for a project
GET  /explanation/{project_id} — retrieve the stored explanation report
"""

from __future__ import annotations

from fastapi import APIRouter

from app.container import ContainerDep
from app.core.errors import ValidationError
from app.explanation.manager import ExplanationRecord
from app.explanation.model import EvidenceReference, WhereReference
from app.runtime.model import RuntimeResult
from app.runtime.service import RuntimeAnalysis
from app.schemas.explanation import (
    EvidenceReferenceSchema,
    ExplanationDetail,
    WhereReferenceSchema,
)

router = APIRouter(prefix="/explanation", tags=["explanation"])


@router.post(
    "/{project_id}",
    response_model=ExplanationDetail,
    summary="Generate an explanation for a project",
)
def run_explanation(project_id: str, container: ContainerDep) -> ExplanationDetail:
    """Explain the stored localization result for ``project_id``."""
    project = container.repository_manager.get_project(project_id)
    localization = container.localization_manager.get(project.id)
    if localization.result is None:
        raise ValidationError(
            reason="No localization result to explain",
            module="Explanation API",
            detail={"project_id": project_id},
        )
    knowledge = container.knowledge_manager.get(project.id)
    graph = knowledge.graph.graph if knowledge.graph else None
    runtime = container.runtime_manager.latest_ready(project.id)
    runtime_result = _pick_runtime_result(runtime.result if runtime else None)
    record = container.explanation_manager.explain(
        project.id,
        localization.result,
        graph=graph,
        runtime=runtime_result,
    )
    return _to_detail(record)


@router.get(
    "/{project_id}",
    response_model=ExplanationDetail,
    summary="Retrieve the stored explanation report",
)
def get_explanation(project_id: str, container: ContainerDep) -> ExplanationDetail:
    """Return the stored explanation report for ``project_id``."""
    record = container.explanation_manager.get(project_id)
    return _to_detail(record)


def _pick_runtime_result(runtime: RuntimeAnalysis | None) -> RuntimeResult | None:
    """Return the runtime result carrying a crash, else the first available."""
    if runtime is None:
        return None
    candidates = list(runtime.results.values())
    for candidate in candidates:
        if candidate.exception is not None:
            return candidate
    return candidates[0] if candidates else None


def _to_detail(record: ExplanationRecord) -> ExplanationDetail:
    report = record.report
    return ExplanationDetail(
        project_id=record.project_id,
        status=record.status.value,
        created_at=record.created_at,
        updated_at=record.updated_at,
        error=record.error,
        resolved=report.resolved if report else False,
        error_summary=report.error_summary if report else "",
        root_cause=report.root_cause if report else None,
        why=report.why if report else "",
        where=[_to_where(item) for item in report.where] if report else [],
        evidence=[_to_evidence(item) for item in report.evidence] if report else [],
        suggested_fix=report.suggested_fix if report else None,
        confidence=report.confidence if report else 0.0,
        propagation_path=list(report.propagation_path) if report else [],
        missing_sources=list(report.missing_sources) if report else [],
        insufficient_evidence=report.insufficient_evidence if report else False,
    )


def _to_evidence(item: EvidenceReference) -> EvidenceReferenceSchema:
    return EvidenceReferenceSchema(
        source=item.source,
        description=item.description,
        score=item.score,
        artifact=item.artifact,
    )


def _to_where(item: WhereReference) -> WhereReferenceSchema:
    return WhereReferenceSchema(
        file=item.file,
        function=item.function,
        cls=item.cls,
        line=item.line,
    )
