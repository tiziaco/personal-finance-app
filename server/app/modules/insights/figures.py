"""The only reader of analytics: gathers one user's figures and builds the insights agent's input.

Windows (analytics.md §2, PR #16): `months=N` counts the last N finished months, anchored at the latest
finished month with data, which is the dashboard's reference month. So `months=1` is the reference month and
`months=BASELINE_MONTHS + 1` is the reference month plus up to six before it. The month in progress is read
apart, as month-to-date, with explicit bounds.
"""

import calendar
import datetime as dt
import uuid
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.insights import InsightsInput
from app.modules.analytics import DateRange, analytics_service
from app.modules.transaction import CATEGORIES

BASELINE_MONTHS = 6
TOP_N = 10
ANOMALY_STD_THRESHOLD = 2.5
ANOMALY_WINDOW_DAYS = 30


@dataclass(frozen=True)
class Gathered:
    """The agent's input, and how many baseline months stand behind it."""

    input: InsightsInput
    baseline_months: int


def _merchants(node: Any) -> set[str]:
    """Every string value under a key named `merchant`, anywhere in the figures."""
    found: set[str] = set()
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "merchant" and isinstance(value, str):
                found.add(value)
            else:
                found |= _merchants(value)
    elif isinstance(node, list):
        for item in node:
            found |= _merchants(item)
    return found


def _same_days_previous_month(through: dt.date) -> tuple[dt.date, dt.date]:
    """Days 1 to through's day of the month before, clamped to that month's length."""
    last_of_previous = through.replace(day=1) - dt.timedelta(days=1)
    day = min(through.day, last_of_previous.day)
    return last_of_previous.replace(day=1), last_of_previous.replace(day=day)


async def gather_figures(session: AsyncSession, user_id: uuid.UUID) -> Optional[Gathered]:
    """The figures for the user's reference month; None when they have no data."""
    dashboard = await analytics_service.dashboard(session, user_id)
    if dashboard.reference_month is None:
        return None

    one = DateRange(months=1)
    seven = DateRange(months=BASELINE_MONTHS + 1)
    spending = await analytics_service.spending(session, user_id, seven)
    behaviour = (await analytics_service.behaviour(session, user_id, seven)).model_dump(mode="json")
    behaviour.pop("seasonality", None)  # a year-shaped series that says nothing about this month

    spending_json = spending.model_dump(mode="json")
    spending_json.pop("month_to_date", None)  # the dashboard's block carries it, once
    figures: dict[str, Any] = {
        "dashboard": dashboard.model_dump(mode="json", exclude={"month_to_date"}),
        "spending": spending_json,
        "categories_month": (await analytics_service.categories(session, user_id, one, TOP_N)).model_dump(mode="json"),
        "categories_trend": (await analytics_service.categories(session, user_id, seven, TOP_N)).model_dump(
            mode="json"
        ),
        "merchants": (await analytics_service.merchants(session, user_id, one, TOP_N)).model_dump(mode="json"),
        "recurring": (await analytics_service.recurring(session, user_id, seven)).model_dump(mode="json"),
        "behaviour": behaviour,
        "anomalies": (
            await analytics_service.anomalies(session, user_id, one, ANOMALY_STD_THRESHOLD, ANOMALY_WINDOW_DAYS)
        ).model_dump(mode="json"),
    }

    month_to_date = dashboard.month_to_date
    through: Optional[dt.date] = None
    if dashboard.reference_partial:
        # The month in progress is the reference month: one month, not two. Say how far it runs.
        if month_to_date is not None:
            figures["reference_through"] = month_to_date.through.isoformat()
    elif month_to_date is not None:
        through = month_to_date.through
        figures["month_to_date"] = month_to_date.model_dump(mode="json")
        previous_from, previous_to = _same_days_previous_month(through)
        figures["categories_month_to_date"] = (
            await analytics_service.categories(
                session, user_id, DateRange(date_from=through.replace(day=1), date_to=through), TOP_N
            )
        ).model_dump(mode="json")
        figures["categories_month_to_date_previous"] = (
            await analytics_service.categories(
                session, user_id, DateRange(date_from=previous_from, date_to=previous_to), TOP_N
            )
        ).model_dump(mode="json")

    baseline = sum(
        1 for month in spending.months if month.month < dashboard.reference_month and (month.income or month.expenses)
    )

    return Gathered(
        input=InsightsInput(
            reference_month=dashboard.reference_month,
            reference_partial=dashboard.reference_partial,
            month_to_date_through=through,
            figures=figures,
            categories=list(CATEGORIES),
            merchants=frozenset(_merchants(figures)),
        ),
        baseline_months=min(baseline, BASELINE_MONTHS),
    )
