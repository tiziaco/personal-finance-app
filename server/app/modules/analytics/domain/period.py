"""Periods: the calendar days and months a figure covers, resolved from a request and the data (spec §3)."""

import datetime as dt
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from app.modules.analytics.domain._aggregate import R, add_months, month_end, month_range, month_start

FIRST_MONTH_GRACE_DAYS = 7
ONE_DAY = dt.timedelta(days=1)


@dataclass(frozen=True)
class PeriodMonth:
    """One calendar month of a period: the days of it covered and their share of the month."""

    start: dt.date
    first_day: dt.date
    last_day: dt.date
    partial: bool
    weight: Decimal


@dataclass(frozen=True)
class Period:
    """Consecutive calendar months, the first and last possibly partial."""

    first_day: dt.date
    last_day: dt.date
    months: tuple[PeriodMonth, ...]

    def weight(self) -> Decimal:
        """The sum of month weights: the period's length in months."""
        return sum((m.weight for m in self.months), Decimal(0))

    def whole_months(self) -> tuple[PeriodMonth, ...]:
        """The months no rule cut."""
        return tuple(m for m in self.months if not m.partial)

    def contains(self, day: dt.date) -> bool:
        """Whether day falls between the first and last day."""
        return self.first_day <= day <= self.last_day

    def rows(self, rows: Iterable[R]) -> list[R]:
        """The rows dated inside the period."""
        return [r for r in rows if self.contains(r.date)]


def usable_rows(rows: Iterable[R], today: dt.date) -> list[R]:
    """Rows dated no later than the last day of the current month; anything later is a typo or scheduled."""
    limit = month_end(today)
    return [r for r in rows if r.date <= limit]


def data_span(rows: Iterable[R], today: dt.date) -> Optional[tuple[dt.date, dt.date]]:
    """The first and last usable day; None without usable rows."""
    days = [r.date for r in usable_rows(rows, today)]
    if not days:
        return None
    return min(days), max(days)


def anchor_month(rows: Iterable[R], today: dt.date) -> Optional[dt.date]:
    """The latest finished month holding a usable row, else the current month if it holds one."""
    current = month_start(today)
    held = {month_start(r.date) for r in usable_rows(rows, today)}
    finished = [m for m in held if m < current]
    if finished:
        return max(finished)
    return current if current in held else None


def calendar_month(month: dt.date, rows: Iterable[R], today: dt.date) -> Optional[PeriodMonth]:
    """The given month as the data sees it (rules 2 and 3); None outside the data's months."""
    span = data_span(rows, today)
    start = month_start(month)
    if span is None or not month_start(span[0]) <= start <= month_start(span[1]):
        return None
    return _month(start, start, month_end(start), span, today)


def resolve_period(
    rows: Iterable[R],
    today: dt.date,
    *,
    date_from: Optional[dt.date] = None,
    date_to: Optional[dt.date] = None,
    months: Optional[int] = None,
) -> Optional[Period]:
    """The period a request covers (spec §3.2); None without usable rows or for a range outside the data."""
    rows = list(rows)
    span = data_span(rows, today)
    anchor = anchor_month(rows, today)
    if span is None or anchor is None:
        return None
    first_month, last_month = month_start(span[0]), month_start(span[1])
    if date_from is None and date_to is None:
        start = first_month if months is None else max(add_months(anchor, 1 - months), first_month)
        end = month_end(anchor)
    elif months is not None:
        raise ValueError("months cannot be combined with date_from or date_to")
    else:
        start = max(date_from or first_month, first_month)
        end = min(date_to or month_end(last_month), month_end(last_month))  # usable rows end by today's month
    if start > end:
        return None
    built = (_month(m, max(start, m), min(end, month_end(m)), span, today) for m in month_range(start, end))
    period_months = tuple(m for m in built if m is not None)
    if not period_months:
        return None
    return Period(period_months[0].first_day, period_months[-1].last_day, period_months)


def previous_period(period: Period, rows: Iterable[R], today: dt.date) -> Optional[Period]:
    """The span before period: as many months when it is month-aligned, else as many days; None without rows."""
    rows = list(rows)
    first, last = period.first_day, period.last_day
    if first.day == 1 and last == month_end(last):
        date_from, date_to = add_months(first, -len(period.months)), first - ONE_DAY
    else:
        date_to = first - ONE_DAY
        date_from = date_to - (last - first)
    previous = resolve_period(rows, today, date_from=date_from, date_to=date_to)
    if previous is None or not previous.rows(rows):
        return None
    return previous


def _month(
    start: dt.date, first_day: dt.date, last_day: dt.date, span: tuple[dt.date, dt.date], today: dt.date
) -> Optional[PeriodMonth]:
    """The month at start over first_day..last_day, narrowed by rules 2 and 3; None when no day is left."""
    data_first, data_last = span
    if start == month_start(today):
        last_day = min(last_day, data_last)
    if start == month_start(data_first) and data_first.day > FIRST_MONTH_GRACE_DAYS:
        first_day = max(first_day, data_first)
    if first_day > last_day:
        return None
    end = month_end(start)
    partial = first_day != start or last_day != end
    weight = Decimal((last_day - first_day).days + 1) / Decimal(end.day) if partial else Decimal(1)
    return PeriodMonth(start, first_day, last_day, partial, weight)
