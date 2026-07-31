"""Pydantic schemas for the knowledge graph API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.analysis import GraphEdgeSchema, GraphNodeSchema


class KnowledgeBuildRequest(BaseModel):
    """Request body for building a project's unified knowledge graph."""

    project_id: str = Field(min_length=1)


class KnowledgeStats(BaseModel):
    """Node and edge statistics for a knowledge graph."""

    node_count: int = 0
    edge_count: int = 0
    node_kinds: dict[str, int] = Field(default_factory=dict)
    edge_kinds: dict[str, int] = Field(default_factory=dict)


class KnowledgeSummary(BaseModel):
    """Lifecycle state of one knowledge graph build."""

    project_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    error: str | None = None
    sources: list[str] = Field(default_factory=list)
    missing_sources: list[str] = Field(default_factory=list)


class KnowledgeDetail(KnowledgeSummary):
    """A knowledge graph build including the unified graph payload."""

    stats: KnowledgeStats = Field(default_factory=KnowledgeStats)
    nodes: list[GraphNodeSchema] = Field(default_factory=list)
    edges: list[GraphEdgeSchema] = Field(default_factory=list)
