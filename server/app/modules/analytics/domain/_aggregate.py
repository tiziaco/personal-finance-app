"""Shared helpers: the row the library reads, money, months, grouping and safe ratios."""

import calendar
import datetime as dt
from collections.abc import Callable, Hashable, Iterable, Sequence
from decimal import ROUND_HALF_UP, Decimal
from statistics import mean, pstdev
from typing import Optional, Protocol, TypeVar

CENT = Decimal("0.01")
ZERO = Decimal("0.00")
AVERAGE_MONTH_DAYS = Decimal("30.436875")  # 365.2425 / 12


class Row(Protocol):
    """One transaction as the library reads it. transaction's AnalysisRow satisfies it."""

    @property
    def date(self) -> dt.date: ...

    @property
    def merchant(self) -> str: ...

    @property
    def merchant_key(self) -> str:
        """The stored merchant key (data-model/transaction.md, D7): rows sharing one are one merchant."""
        ...

    @property
    def amount(self) -> Decimal: ...

    @property
    def category(self) -> str: ...

    @property
    def is_recurring(self) -> bool: ...


R = TypeVar("R", bound=Row)
K = TypeVar("K", bound=Hashable)


def money(value: Decimal) -> Decimal:
    """Quantise to cents, half-up; -0.00 becomes 0.00."""
    cents = value.quantize(CENT, rounding=ROUND_HALF_UP)
    return ZERO if cents == 0 else cents


def expenses(rows: Iterable[R]) -> list[R]:
    """Money out: a negative amount."""
    return [r for r in rows if r.amount < 0]


def incomes(rows: Iterable[R]) -> list[R]:
    """Money in: a positive amount. A zero amount is neither."""
    return [r for r in rows if r.amount > 0]


def spend(row: Row) -> Decimal:
    """An expense as a positive amount."""
    return -row.amount


def total_spend(rows: Iterable[Row]) -> Decimal:
    """The sum of expenses, positive."""
    return money(sum((spend(r) for r in rows), ZERO))


def total_amount(rows: Iterable[Row]) -> Decimal:
    """The sum of signed amounts."""
    return money(sum((r.amount for r in rows), ZERO))


def month_start(day: dt.date) -> dt.date:
    """The first day of day's month."""
    return day.replace(day=1)


def month_end(day: dt.date) -> dt.date:
    """The last day of day's month."""
    return day.replace(day=calendar.monthrange(day.year, day.month)[1])


def month_key(month: dt.date) -> str:
    """The month as YYYY-MM, its form on the wire."""
    return f"{month:%Y-%m}"


def add_months(month: dt.date, n: int) -> dt.date:
    """The first day of the month n months from month's (n may be negative)."""
    index = month.year * 12 + month.month - 1 + n
    index = max(dt.date.min.year * 12, min(index, dt.date.max.year * 12 + 11))  # stay inside years 1..9999
    return dt.date(index // 12, index % 12 + 1, 1)


def month_range(first: dt.date, last: dt.date) -> list[dt.date]:
    """Every month start from first's month to last's, inclusive; empty if last precedes first."""
    months: list[dt.date] = []
    current, end = month_start(first), month_start(last)
    while current <= end:
        months.append(current)
        if current == end:  # stepping past the last month could leave the calendar (December 9999)
            break
        current = add_months(current, 1)
    return months


def span(
    rows: Sequence[Row], date_from: Optional[dt.date], date_to: Optional[dt.date]
) -> Optional[tuple[dt.date, dt.date]]:
    """The days a result covers: the given bounds, else the data's first and last day; None when unknown."""
    start = date_from or min((r.date for r in rows), default=None)
    end = date_to or max((r.date for r in rows), default=None)
    if start is None or end is None or end < start:
        return None
    return start, end


def group_by(rows: Iterable[R], key: Callable[[R], K]) -> dict[K, list[R]]:
    """Rows grouped by key, groups in first-seen order."""
    groups: dict[K, list[R]] = {}
    for row in rows:
        groups.setdefault(key(row), []).append(row)
    return groups


def monthly_totals(rows: Iterable[R], months: Sequence[dt.date], value: Callable[[R], Decimal]) -> list[Decimal]:
    """The sum of value(row) for each month in months; zero for a month without rows."""
    by_month = group_by(rows, lambda r: month_start(r.date))
    return [money(sum((value(r) for r in by_month.get(m, [])), ZERO)) for m in months]


def pct_change(old: Decimal, new: Decimal) -> Optional[float]:
    """Percent change from old to new; None when old is zero."""
    if old == 0:
        return None
    return round(float((new - old) / old * 100), 2)


def share_pct(part: Decimal, whole: Decimal) -> float:
    """Part as a percent of whole; 0 when whole is zero."""
    if whole == 0:
        return 0.0
    return round(float(part / whole * 100), 2)


def average(total: Decimal, count: int) -> Decimal:
    """Total ÷ count in cents; zero for no items."""
    return money(total / count) if count else ZERO


def cv(values: Sequence[Decimal]) -> Optional[float]:
    """Coefficient of variation, population stdev ÷ mean; None for fewer than two values or a zero mean."""
    if len(values) < 2:
        return None
    centre = mean(values)
    if centre == 0:
        return None
    return round(float(pstdev(values) / centre), 4)
