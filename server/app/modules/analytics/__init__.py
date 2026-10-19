"""Analytics — every calculation over the user's transactions. Stores nothing.

This is the public surface. Another module imports from here and nowhere
deeper (docs/architecture/server.md, R1).
"""

from app.modules.analytics.exceptions import InvalidDateRangeError
from app.modules.analytics.history import AnalyticsHistory
from app.modules.analytics.router import router
from app.modules.analytics.schemas import (
    AnomaliesResponse,
    BehaviourResponse,
    CategoryBreakdownResponse,
    DashboardResponse,
    DateRange,
    LatestMonthResponse,
    MerchantBreakdownResponse,
    MonthToDateResponse,
    RecurringResponse,
    SpendingResponse,
)
from app.modules.analytics.service import analytics_service

__all__ = [
    "AnalyticsHistory",
    "AnomaliesResponse",
    "BehaviourResponse",
    "CategoryBreakdownResponse",
    "DashboardResponse",
    "DateRange",
    "InvalidDateRangeError",
    "LatestMonthResponse",
    "MerchantBreakdownResponse",
    "MonthToDateResponse",
    "RecurringResponse",
    "SpendingResponse",
    "analytics_service",
    "router",
]
