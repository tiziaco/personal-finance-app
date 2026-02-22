"""Request filters and response schemas for the analytics API."""

from datetime import date, datetime
from typing import Any, Dict, Optional

from fastapi import Query
from pydantic import BaseModel


class AnalyticsFilters:
    """Common date-range query params. Injected via Depends() on all endpoints."""

    def __init__(
        self,
        date_from: Optional[date] = Query(
            None, description="Inclusive start date filter (YYYY-MM-DD)"
        ),
        date_to: Optional[date] = Query(
            None, description="Inclusive end date filter (YYYY-MM-DD)"
        ),
    ):
        self.date_from = date_from
        self.date_to = date_to


class AnalyticsResponse(BaseModel):
    """Generic envelope returned by all single-domain analytics endpoints."""

    data: Dict[str, Any]
    generated_at: datetime


class DashboardResponse(BaseModel):
    """Composed response for GET /analytics/dashboard."""

    spending: Dict[str, Any]
    categories: Dict[str, Any]
    recurring: Dict[str, Any]
    trends: Dict[str, Any]
    generated_at: datetime
