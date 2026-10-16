"""The home page's figures: the latest month with data, its cards, its categories, and the trend to it."""

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from app.modules.analytics.domain._aggregate import (
    ZERO,
    Row,
    add_months,
    expenses,
    money,
    month_key,
    month_range,
    month_start,
    share_pct,
    total_spend,
)
from app.modules.analytics.domain.categories import category_spend
from app.modules.analytics.domain.period import PeriodMonth, anchor_month, calendar_month, usable_rows
from app.modules.analytics.domain.spending import MonthToDate, month_to_date, monthly_flows

TOP_SLICES = 5
CASHFLOW_MONTHS = 3
TREND_MONTHS = 6


@dataclass(frozen=True)
class CategorySlice:
    """One slice of the spending chart; a None category is the "Other" slice."""

    category: Optional[str]
    amount: Decimal
    share_pct: float


@dataclass(frozen=True)
class TrendPoint:
    """One month of the trend chart: income and expenses."""

    month: str
    income: Decimal
    expenses: Decimal


@dataclass(frozen=True)
class Dashboard:
    """Every figure the home page draws, anchored to the reference month."""

    reference_month: Optional[str]
    reference_partial: bool
    total_spent: Decimal
    recurring_spent: Decimal
    recurring_count: int
    net_balance: Decimal
    average_cashflow: Decimal
    cashflow_months: int
    spending_by_category: tuple[CategorySlice, ...]
    monthly_trend: tuple[TrendPoint, ...]
    month_to_date: Optional[MonthToDate]


EMPTY = Dashboard(None, False, ZERO, ZERO, 0, ZERO, ZERO, 0, (), (), None)


def _slices(month_rows: Sequence[Row], total: Decimal) -> tuple[CategorySlice, ...]:
    ranked = category_spend(month_rows)
    slices = [CategorySlice(c.category, c.total, share_pct(c.total, total)) for c in ranked[:TOP_SLICES]]
    rest = ranked[TOP_SLICES:]
    if rest:
        other = money(sum((c.total for c in rest), ZERO))
        slices.append(CategorySlice(None, other, share_pct(other, total)))
    return tuple(slices)


def _months(rows: Sequence[Row], months: Sequence[dt.date], today: dt.date) -> list[PeriodMonth]:
    """The months as the data sees them; every month asked for lies inside the data."""
    return [month for m in months if (month := calendar_month(m, rows, today)) is not None]


def build_dashboard(rows: Sequence[Row], *, today: dt.date) -> Dashboard:
    """Everything the home page draws.

    The reference month is the anchor month: the latest finished month holding a usable row, else the
    current month (then partial). Rows dated after the current month are ignored. The trend runs six
    months to the reference but not before the data's first month.
    """
    rows = usable_rows(rows, today)
    reference = anchor_month(rows, today)
    if reference is None:
        return EMPTY
    first = month_start(min(r.date for r in rows))
    month_rows = [r for r in rows if month_start(r.date) == reference]
    spent = expenses(month_rows)
    flagged = [r for r in spent if r.is_recurring]
    total = total_spend(spent)

    cashflow_window = month_range(max(first, add_months(reference, -(CASHFLOW_MONTHS - 1))), reference)
    cashflow = monthly_flows(rows, _months(rows, cashflow_window, today), today=today)
    trend_window = month_range(max(first, add_months(reference, -(TREND_MONTHS - 1))), reference)
    trend = monthly_flows(rows, _months(rows, trend_window, today), today=today)

    return Dashboard(
        reference_month=month_key(reference),
        reference_partial=reference == month_start(today),
        total_spent=total,
        recurring_spent=total_spend(flagged),
        recurring_count=len(flagged),
        net_balance=cashflow[-1].net,
        average_cashflow=money(sum((m.net for m in cashflow), ZERO) / len(cashflow)),
        cashflow_months=len(cashflow),
        spending_by_category=_slices(month_rows, total),
        monthly_trend=tuple(TrendPoint(m.month, m.income, m.expenses) for m in trend),
        month_to_date=month_to_date(rows, today),
    )
