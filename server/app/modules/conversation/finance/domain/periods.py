"""Periods named the way the dashboard and the analytics page name them (analytics.md §2).

Whole months by month ("September 2026", "Jul – Sep 2026"), anything else by day
("3 – 19 Sep 2026"); a period that runs to the data's end in the month in progress
reads "so far". Month names are fixed English, never the server's locale.
"""

import datetime as dt
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.modules.analytics import AnalyticsHistory, DateRange

MONTH_NAMES = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
SHORT_MONTH_NAMES = tuple(name[:3] for name in MONTH_NAMES)
DASH = " – "


def month_name(day: dt.date) -> str:
    """The month a day falls in, in full: "September 2026"."""
    return f"{MONTH_NAMES[day.month - 1]} {day.year}"


def short_month(month: str) -> str:
    """A "YYYY-MM" month as a table names it: "Sep 2026"."""
    year, number = month.split("-")
    return f"{SHORT_MONTH_NAMES[int(number) - 1]} {year}"


def _month_end(day: dt.date) -> dt.date:
    first_of_next = (day.replace(day=1) + dt.timedelta(days=32)).replace(day=1)
    return first_of_next - dt.timedelta(days=1)


def _by_month(first_day: dt.date, last_day: dt.date) -> str:
    if (first_day.year, first_day.month) == (last_day.year, last_day.month):
        return month_name(first_day)
    first, last = SHORT_MONTH_NAMES[first_day.month - 1], SHORT_MONTH_NAMES[last_day.month - 1]
    if first_day.year == last_day.year:
        return f"{first}{DASH}{last} {last_day.year}"
    return f"{first} {first_day.year}{DASH}{last} {last_day.year}"


def _by_day(first_day: dt.date, last_day: dt.date) -> str:
    last = f"{last_day.day} {SHORT_MONTH_NAMES[last_day.month - 1]} {last_day.year}"
    if first_day == last_day:
        return last
    if (first_day.year, first_day.month) == (last_day.year, last_day.month):
        return f"{first_day.day}{DASH}{last}"
    first = f"{first_day.day} {SHORT_MONTH_NAMES[first_day.month - 1]}"
    if first_day.year == last_day.year:
        return f"{first}{DASH}{last}"
    return f"{first} {first_day.year}{DASH}{last}"


def name_period(first_day: dt.date, last_day: dt.date, *, so_far: bool = False) -> str:
    """Name an inclusive span of days; `so_far` when it ends at the data's end in the month in progress."""
    whole_months = first_day.day == 1 and (so_far or last_day == _month_end(last_day))
    name = _by_month(first_day, last_day) if whole_months else _by_day(first_day, last_day)
    return f"{name} so far" if so_far else name


def data_span(history: "AnalyticsHistory") -> Optional[tuple[dt.date, dt.date]]:
    """The first and last day holding a transaction; None without any."""
    if not history.rows:
        return None
    days = [r.date for r in history.rows]
    return min(days), max(days)


def describe_span(first_day: dt.date, last_day: dt.date) -> str:
    """The months the data covers, for a message to the model: "data covers March 2025 to October 2026"."""
    return f"data covers {month_name(first_day)} to {month_name(last_day)}"


def period_label(history: "AnalyticsHistory", date_range: "DateRange") -> str:
    """The name of the period a range resolves to over the history, as the analytics page shows it.

    Raises ValueError for a range that resolves to nothing: callers validate it first (`to_date_range`).
    """
    period = history.period(date_range)
    span = data_span(history)
    if period is None or span is None:
        raise ValueError("the range resolves to no period")
    in_progress = (period.last_day.year, period.last_day.month) == (history.today.year, history.today.month)
    return name_period(period.first_day, period.last_day, so_far=in_progress and period.last_day == span[1])
