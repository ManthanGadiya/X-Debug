"""Bug localization endpoints.

POST /localization/{project_id} — run localization for a project
GET  /localization/{project_id} — retrieve the stored localization result
"""

from __future__ import annotations

from fastapi import APIRouter

from app.container import ContainerDep
from app.core.errors import ValidationError
from app.localization.manager import LocalizationRecord
from app.localization.model import Evidence, LocalizationCandidate
from app.projects.languages import resolve_language
from app.schemas.localization import (
    EvidenceSchema,
    LocalizationCandidateSchema,
    LocalizationDetail,
    LocalizationRequest,
)

router = APIRouter(prefix="/localization", tags=["localization"])


@router.post(
    "/{project_id}",
    response_model=LocalizationDetail,
    summary="Run bug localization for a project",
)
def run_localization(
    project_id: str,
    container: ContainerDep,
    request: LocalizationRequest,
) -> LocalizationDetail:
    """Rank candidate root causes for ``project_id``'s latest crash."""
    language = resolve_language(request.language)
    if language is None:
        raise ValidationError(reason=f"Unsupported language: {request.language!r}")
    canonical = language.value
    project = container.repository_manager.get_project(project_id)
    knowledge = container.knowledge_manager.get(project.id)
    runtime = container.runtime_manager.latest_ready(project.id)
    runtime_result = None
    if runtime is not None and runtime.result is not None:
        runtime_result = runtime.result.results.get(canonical)
    record = container.localization_manager.localize(
        project.id,
        knowledge.graph.graph if knowledge.graph else None,
        runtime_result,
        language=canonical,
    )
    return _to_detail(record)


@router.get(
    "/{project_id}",
    response_model=LocalizationDetail,
    summary="Retrieve the stored localization result",
)
def get_localization(project_id: str, container: ContainerDep) -> LocalizationDetail:
    """Return the stored localization result for ``project_id``."""
    record = container.localization_manager.get(project_id)
    return _to_detail(record)


def _to_detail(record: LocalizationRecord) -> LocalizationDetail:
    result = record.result
    return LocalizationDetail(
        project_id=record.project_id,
        status=record.status.value,
        created_at=record.created_at,
        updated_at=record.updated_at,
        error=record.error,
        resolved=result.resolved if result else False,
        confidence=result.confidence if result else 0.0,
        summary=result.summary if result else "",
        root_cause=_to_candidate(result.root_cause) if result and result.root_cause else None,
        candidates=[_to_candidate(candidate) for candidate in result.candidates] if result else [],
        propagation_path=list(result.propagation_path) if result else [],
        evidence_summary=[_to_evidence(item) for item in result.evidence_summary] if result else [],
        missing_sources=list(result.missing_sources) if result else [],
        suggested_fix=result.suggested_fix if result else None,
    )


def _to_candidate(candidate: LocalizationCandidate) -> LocalizationCandidateSchema:
    return LocalizationCandidateSchema(
        node_id=candidate.node_id,
        label=candidate.label,
        kind=candidate.kind,
        score=candidate.score,
        evidence=[_to_evidence(item) for item in candidate.evidence],
        reason=candidate.reason,
    )


def _to_evidence(item: Evidence) -> EvidenceSchema:
    return EvidenceSchema(
        source=item.source.value,
        description=item.description,
        score=item.score,
    )
