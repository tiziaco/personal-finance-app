"""Insights response schemas."""

import datetime as dt
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field

InsightsStatus = Literal["no_data", "none", "stale", "fresh"]
StaleReason = Literal["new_month", "data_changed"]


class KeyFigureResponse(BaseModel):
    """The card's chip: a number the web formats, and a short qualifier."""

    kind: Literal["amount", "percent", "count"]
    value: Decimal = Field(..., description="The figure, as a decimal string")
    qualifier: str


class InsightLinkResponse(BaseModel):
    """Where the card leads."""

    kind: Literal["recurring", "category", "merchant"]
    category: Optional[str] = None
    merchant: Optional[str] = None


class InsightResponse(BaseModel):
    """One insight."""

    section: Literal["spending", "recurring", "savings", "anomalies", "comparisons"]
    severity: Literal["info", "low", "medium", "high", "critical"]
    period: Literal["month", "month_to_date"]
    summary: str
    narrative: str
    key_figure: Optional[KeyFigureResponse] = None
    link: Optional[InsightLinkResponse] = None


class InsightsResponse(BaseModel):
    """The user's insights and how current they are."""

    status: InsightsStatus = Field(
        ...,
        description="no_data: nothing to analyse; none: never generated; stale: data changed or the month rolled over since; fresh",
    )
    stale_reason: Optional[StaleReason] = Field(
        None,
        description="Set when stale: new_month when a calendar month (UTC) began since, else data_changed",
    )
    generated_at: Optional[dt.datetime] = None
    reference_month: Optional[str] = Field(None, description="YYYY-MM of the finished month the insights describe")
    month_to_date_through: Optional[dt.date] = None
    insights: list[InsightResponse] = Field(default_factory=list)
