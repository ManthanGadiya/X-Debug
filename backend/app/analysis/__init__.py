"""Static analysis subsystem (Phase 3).

Transforms a loaded repository into structural understanding: AST extraction,
dependency graph, call graph, control flow graph, and data flow analysis.
"""

from app.analysis.manager import AnalysisManager as AnalysisManager
from app.analysis.service import AnalysisService as AnalysisService

__all__ = ["AnalysisManager", "AnalysisService"]
