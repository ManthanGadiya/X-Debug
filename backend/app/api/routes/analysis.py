"""Static analysis endpoints.

POST /analysis/start       — start an asynchronous analysis run for a project
GET  /analysis/{id}        — retrieve the lifecycle state and result summary
GET  /analysis/{id}/graphs/{kind} — retrieve one graph from a finished run
"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, Path, status

from app.analysis import AnalysisManager
from app.analysis.graph import Graph
from app.analysis.manager import AnalysisRecord, AnalysisStatus
from app.analysis.service import AnalysisService
from app.container import ContainerDep
from app.schemas.analysis import (
    AnalysisDetail,
    AnalysisStartRequest,
    AnalysisSummary,
    GraphData,
    GraphEdgeSchema,
    GraphNodeSchema,
)

router = APIRouter(prefix="/analysis", tags=["analysis"])

_GRAPH_KINDS = {
    "dependency": "dependency_graph",
    "call": "call_graph",
    "cfg": "cfg",
    "dataflow": "dataflow_graph",
}


@router.get(
    "",
    response_model=list[AnalysisSummary],
    summary="List analysis runs",
)
def list_analysis(container: ContainerDep) -> list[AnalysisSummary]:
    """Return all analysis runs, most recent first."""
    return [_to_summary(record) for record in container.analysis_manager.list()]


@router.post(
    "/start",
    response_model=AnalysisSummary,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start a static analysis run",
)
def start_analysis(
    container: ContainerDep,
    request: AnalysisStartRequest,
    background_tasks: BackgroundTasks,
) -> AnalysisSummary:
    """Queue a static analysis run for a previously ingested project."""
    project = container.repository_manager.get_project(request.project_id)
    record = container.analysis_manager.start(project.id)

    manager: AnalysisManager = container.analysis_manager
    service: AnalysisService = container.analysis_service
    background_tasks.add_task(manager.run, record.id, lambda: service.analyze(project))
    return _to_summary(record)


@router.get(
    "/{analysis_id}",
    response_model=AnalysisDetail,
    summary="Retrieve analysis state and result summary",
)
def get_analysis(
    analysis_id: str,
    container: ContainerDep,
) -> AnalysisDetail:
    """Return the lifecycle state of an analysis run."""
    record = container.analysis_manager.get(analysis_id)
    return _to_detail(record)


@router.get(
    "/{analysis_id}/graphs/{kind}",
    response_model=GraphData,
    summary="Retrieve one graph from a finished analysis",
)
def get_graph(
    analysis_id: str,
    container: ContainerDep,
    kind: str = Path(..., pattern="^(dependency|call|cfg|dataflow)$"),
) -> GraphData:
    """Return the requested graph for a finished analysis run."""
    record = container.analysis_manager.get(analysis_id)
    if record.status != AnalysisStatus.READY or record.result is None:
        raise HTTPException(
            status_code=409,
            detail=f"Analysis is not ready (status={record.status.value})",
        )
    graph = getattr(record.result, _GRAPH_KINDS[kind], None)
    if graph is None:
        raise HTTPException(status_code=404, detail=f"No {kind} graph available")
    return _to_graph(graph)


def _to_summary(record: AnalysisRecord) -> AnalysisSummary:
    return AnalysisSummary(
        id=record.id,
        project_id=record.project_id,
        status=record.status,
        created_at=record.created_at,
        updated_at=record.updated_at,
        error=record.error,
    )


def _to_detail(record: AnalysisRecord) -> AnalysisDetail:
    result = record.result
    return AnalysisDetail(
        id=record.id,
        project_id=record.project_id,
        status=record.status,
        created_at=record.created_at,
        updated_at=record.updated_at,
        error=record.error,
        parsed_file_count=result.parsed_file_count if result else 0,
        failed_file_count=result.failed_file_count if result else 0,
        dependency_edge_count=(
            result.dependency_graph.edge_count if result and result.dependency_graph else 0
        ),
        call_edge_count=result.call_graph.edge_count if result and result.call_graph else 0,
        cfg_node_count=result.cfg.node_count if result and result.cfg else 0,
        dataflow_edge_count=(
            result.dataflow_graph.edge_count if result and result.dataflow_graph else 0
        ),
    )


def _to_graph(graph: Graph) -> GraphData:
    return GraphData(
        name=graph.name,
        node_count=graph.node_count,
        edge_count=graph.edge_count,
        nodes=[
            GraphNodeSchema(id=node.id, kind=node.kind, label=node.label)
            for node in graph.nodes.values()
        ],
        edges=[
            GraphEdgeSchema(source=edge.source, target=edge.target, kind=edge.kind)
            for edge in graph.edges
        ],
    )
