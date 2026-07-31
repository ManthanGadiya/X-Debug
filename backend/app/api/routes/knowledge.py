"""Knowledge graph endpoints.

POST /knowledge/build          — build the unified knowledge graph for a project
GET  /knowledge/{project_id}   — retrieve the stored unified knowledge graph
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.analysis.graph import GraphEdge, GraphNode
from app.analysis.knowledge_manager import KnowledgeRecord
from app.container import ContainerDep
from app.schemas.analysis import GraphEdgeSchema, GraphNodeSchema
from app.schemas.knowledge import KnowledgeBuildRequest, KnowledgeDetail, KnowledgeStats

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post(
    "/build",
    response_model=KnowledgeDetail,
    summary="Build the unified knowledge graph",
)
def build_knowledge(
    container: ContainerDep,
    request: KnowledgeBuildRequest,
) -> KnowledgeDetail:
    """Merge static and runtime evidence into one graph for ``project_id``."""
    project = container.repository_manager.get_project(request.project_id)
    analysis = container.analysis_manager.latest_ready(project.id)
    runtime = container.runtime_manager.latest_ready(project.id)
    record = container.knowledge_manager.build(
        project.id,
        analysis.result if analysis else None,
        runtime.result if runtime else None,
    )
    if record.graph is None:
        raise HTTPException(
            status_code=500,
            detail=record.error or "Knowledge graph build failed",
        )
    return _to_detail(record)


@router.get(
    "/{project_id}",
    response_model=KnowledgeDetail,
    summary="Retrieve the unified knowledge graph",
)
def get_knowledge(project_id: str, container: ContainerDep) -> KnowledgeDetail:
    """Return the stored unified knowledge graph for ``project_id``."""
    record = container.knowledge_manager.get(project_id)
    return _to_detail(record)


def _to_detail(record: KnowledgeRecord) -> KnowledgeDetail:
    graph = record.graph
    return KnowledgeDetail(
        project_id=record.project_id,
        status=record.status.value,
        created_at=record.created_at,
        updated_at=record.updated_at,
        error=record.error,
        sources=list(graph.sources) if graph else [],
        missing_sources=list(graph.missing_sources) if graph else [],
        stats=KnowledgeStats(
            node_count=graph.node_count if graph else 0,
            edge_count=graph.edge_count if graph else 0,
            node_kinds=graph.node_kinds() if graph else {},
            edge_kinds=graph.edge_kinds() if graph else {},
        ),
        nodes=[_to_node(node) for node in graph.graph.nodes.values()] if graph else [],
        edges=[_to_edge(edge) for edge in graph.graph.edges] if graph else [],
    )


def _to_node(node: GraphNode) -> GraphNodeSchema:
    return GraphNodeSchema(id=node.id, kind=node.kind, label=node.label)


def _to_edge(edge: GraphEdge) -> GraphEdgeSchema:
    return GraphEdgeSchema(source=edge.source, target=edge.target, kind=edge.kind)
