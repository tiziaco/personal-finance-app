"""Analytics — every calculation over the user's transactions. Stores nothing.

This is the public surface. Another module imports from here and nowhere
deeper (docs/architecture/server.md, R1).
"""

from app.modules.analytics.router import router
from app.modules.analytics.schemas import (
    AnomaliesResponse,
    BehaviourResponse,
    CategoryBreakdownResponse,
    DashboardResponse,
    DateRange,
    MerchantBreakdownResponse,
    RecurringResponse,
    SpendingResponse,
)
from app.modules.analytics.service import analytics_service

__all__ = [
    "AnomaliesResponse",
    "BehaviourResponse",
    "CategoryBreakdownResponse",
    "DashboardResponse",
    "DateRange",
    "MerchantBreakdownResponse",
    "RecurringResponse",
    "SpendingResponse",
    "analytics_service",
    "router",
]
