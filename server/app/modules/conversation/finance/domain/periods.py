"""Periods named the way the dashboard and the analytics page name them (analytics.md §2).

Whole months by month ("September 2026", "Jul – Sep 2026"), anything else by day
("3 – 19 Sep 2026"); a period that runs to the data's end in the month in progress
reads "so far". Month names are fixed English, never the server's locale.
"""

import datetime as dt

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
    whole_months = first_day.day == 1 and (so_far or (last_day + dt.timedelta(days=1)).day == 1)
    name = _by_month(first_day, last_day) if whole_months else _by_day(first_day, last_day)
    return f"{name} so far" if so_far else name


def describe_span(first_day: dt.date, last_day: dt.date) -> str:
    """The months the data covers, for a message to the model: "data covers March 2025 to October 2026"."""
    return f"data covers {month_name(first_day)} to {month_name(last_day)}"


def period_label(first_day: dt.date, last_day: dt.date, *, today: dt.date, data_last: dt.date) -> str:
    """The name of a resolved period, as the analytics page shows it.

    It reads "so far" when it ends at the data's last day in the month in progress.
    """
    in_progress = (last_day.year, last_day.month) == (today.year, today.month)
    return name_period(first_day, last_day, so_far=in_progress and last_day == data_last)
