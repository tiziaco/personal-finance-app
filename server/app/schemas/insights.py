"""Schemas for the insights API."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class InsightType(str, Enum):
    SPENDING_BEHAVIOR = "spending_behavior"
    RECURRING_SUBSCRIPTIONS = "recurring_subscriptions"
    TREND = "trend"
    BEHAVIORAL = "behavioral"
    MERCHANT = "merchant"
    STABILITY = "stability"
    ANOMALY = "anomaly"


class SeverityLevel(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class InsightItem(BaseModel):
    """A single AI-generated financial insight."""

    insight_id: str
    type: InsightType
    severity: SeverityLevel
    time_window: str
    summary: str
    narrative_analysis: Optional[str] = None
    supporting_metrics: Dict[str, Any]
    confidence: float
    section: str


class InsightsResponse(BaseModel):
    """Envelope for GET /api/v1/insights."""

    insights: List[InsightItem]
    generated_at: datetime
