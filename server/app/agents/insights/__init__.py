"""
Insights Graph - Personal Finance Intelligence Engine

Generates deterministic financial insights from transaction data for dashboard consumption.
"""

from .agent import generate_insights, generate_insights_sync, build_insights_graph
from .state import InsightsConfig, InsightsState
from app.schemas.insights import Insight, InsightType, SeverityLevel

__all__ = [
    "generate_insights",
    "generate_insights_sync",
    "build_insights_graph",
    "Insight",
    "InsightType",
    "SeverityLevel",
    "InsightsConfig",
    "InsightsState",
]
