"""Static analysis subsystem (Phase 3).

Transforms a loaded repository into structural understanding: AST extraction,
dependency graph, call graph, control flow graph, and data flow analysis.
"""

from app.analysis.callgraph import CallGraphBuilder as CallGraphBuilder
from app.analysis.cfg import CFGBuilder as CFGBuilder
from app.analysis.dataflow import DataFlowAnalyzer as DataFlowAnalyzer
from app.analysis.dependency import DependencyGraphBuilder as DependencyGraphBuilder
from app.analysis.graph import Graph as Graph
from app.analysis.graph import GraphEdge as GraphEdge
from app.analysis.graph import GraphNode as GraphNode
from app.analysis.model import ClassDef, FunctionDef, ImportRecord, ModuleAST, VariableRecord
from app.analysis.parsers.base import Parser as Parser
from app.analysis.parsers.base import ParserRegistry as ParserRegistry
from app.analysis.service import AnalysisResult
from app.analysis.service import AnalysisService as AnalysisService

__all__ = [
    "AnalysisResult",
    "AnalysisService",
    "CallGraphBuilder",
    "CFGBuilder",
    "ClassDef",
    "DataFlowAnalyzer",
    "DependencyGraphBuilder",
    "FunctionDef",
    "Graph",
    "GraphEdge",
    "GraphNode",
    "ImportRecord",
    "ModuleAST",
    "Parser",
    "ParserRegistry",
    "VariableRecord",
]
