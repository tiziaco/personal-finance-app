"""Periods named the way the dashboard and the analytics page name them (analytics.md §2).

Whole months by month ("September 2026", "Jul – Sep 2026"), anything else by day
("3 – 19 Sep 2026"); a period that runs to the data's end in the month in progress
reads "so far". Month names are fixed English, never the server's locale.

`resolve_period` and `preamble` apply them to the user's history: what a tool covers, and what the model is told.
"""

import datetime as dt
from typing import TYPE_CHECKING

from langchain_core.tools import ToolException

from app.agents.chatbot.context import TurnContext
from app.modules.analytics import AnalyticsHistory, DateRange
from app.modules.conversation.tools.base import NO_TRANSACTIONS, turn_history

if TYPE_CHECKING:
    from app.modules.conversation.tools.analytics import PeriodArgs

ONE_DAY = dt.timedelta(days=1)

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


def resolve_period(args: "PeriodArgs", history: AnalyticsHistory) -> tuple[DateRange, str]:
    """The analytics range for the tool's period and its name; a `ToolException` naming the data span when it holds no data."""
    span = history.span()
    if span is None:
        raise ToolException(NO_TRANSACTIONS)
    covers = describe_span(*span)
    if args.date_from and args.date_to and args.date_from > args.date_to:
        raise ToolException(
            f"date_from {args.date_from.isoformat()} is after date_to {args.date_to.isoformat()}; the {covers}."
        )
    if args.months is not None:
        date_range = DateRange(months=args.months)
    else:
        date_range = DateRange(date_from=args.date_from, date_to=args.date_to)
    period = history.period(date_range)
    if period is None:
        asked = f"{args.date_from.isoformat() if args.date_from else 'the start'} to " + (
            args.date_to.isoformat() if args.date_to else "the end"
        )
        raise ToolException(f"No transactions from {asked}: the {covers}.")
    return date_range, period_label(period.first_day, period.last_day, today=history.today, data_last=span[1])


async def preamble(ctx: TurnContext) -> str:
    """What the model is told about the user's data each turn: the last finished month and the span covered.

    The calendar's last finished month and the dashboard's differ after a month with no
    transactions: `months` counts back from the latest finished month holding one, so the
    model is told both, or it would call that month "last month".
    """
    history = await turn_history(ctx)
    span = history.span()
    if span is None:
        return NO_TRANSACTIONS
    # The dashboard's reference month: the latest finished month holding a transaction.
    reference = history.period(DateRange(months=1))
    last_day = reference.last_day
    label = period_label(reference.first_day, last_day, today=history.today, data_last=span[1])
    if (last_day.year, last_day.month) == (history.today.year, history.today.month):
        return f"No month has finished yet: the user's data covers only {label}."
    last_finished_end = history.today.replace(day=1) - ONE_DAY
    # A finished month's period runs to its last day, so the gap starts the day after.
    gap_start = last_day + ONE_DAY
    if gap_start > last_finished_end:
        return f"Last finished month: {label}; {describe_span(*span)}."
    return (
        f"Last finished month: {month_name(last_finished_end)}. There are no transactions in "
        f"{name_period(gap_start, last_finished_end)}; the latest finished month with transactions is {label}, "
        f"and `months` counts back from it. The {describe_span(*span)}."
    )
