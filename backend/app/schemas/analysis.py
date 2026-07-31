"""Pydantic schemas for the static analysis API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.analysis.manager import AnalysisStatus


class AnalysisStartRequest(BaseModel):
    """Request body for starting an analysis run."""

    project_id: str = Field(min_length=1)


class AnalysisSummary(BaseModel):
    """Lifecycle state of one analysis run."""

    id: str
    project_id: str
    status: AnalysisStatus
    created_at: datetime
    updated_at: datetime
    error: str | None = None


class AnalysisDetail(AnalysisSummary):
    """An analysis run including result statistics."""

    parsed_file_count: int = 0
    failed_file_count: int = 0
    dependency_edge_count: int = 0
    call_edge_count: int = 0
    cfg_node_count: int = 0
    dataflow_edge_count: int = 0


class GraphNodeSchema(BaseModel):
    """Serializable graph node."""

    id: str
    kind: str
    label: str = ""


class GraphEdgeSchema(BaseModel):
    """Serializable graph edge."""

    source: str
    target: str
    kind: str


class GraphData(BaseModel):
    """Serializable graph payload."""

    name: str
    node_count: int
    edge_count: int
    nodes: list[GraphNodeSchema] = Field(default_factory=list)
    edges: list[GraphEdgeSchema] = Field(default_factory=list)
