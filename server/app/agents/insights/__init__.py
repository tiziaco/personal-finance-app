"""The insights writer (docs/product/features/insights.md)."""

from app.agents.insights.writer import (
    MAX_INSIGHTS,
    PROMPT_VERSION,
    InsightLink,
    InsightsInput,
    KeyFigure,
    Period,
    Section,
    Severity,
    WrittenInsight,
    write_insights,
)

__all__ = [
    "MAX_INSIGHTS",
    "PROMPT_VERSION",
    "InsightLink",
    "InsightsInput",
    "KeyFigure",
    "Period",
    "Section",
    "Severity",
    "WrittenInsight",
    "write_insights",
]
