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
from app.modules.analytics.domain.spending import monthly_flows

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
    total_spent: Decimal
    recurring_spent: Decimal
    recurring_count: int
    net_balance: Decimal
    average_cashflow: Decimal
    cashflow_months: int
    spending_by_category: tuple[CategorySlice, ...]
    monthly_trend: tuple[TrendPoint, ...]


EMPTY = Dashboard(None, ZERO, ZERO, 0, ZERO, ZERO, 0, (), ())


def _slices(month_rows: Sequence[Row], total: Decimal) -> tuple[CategorySlice, ...]:
    ranked = category_spend(month_rows)
    slices = [CategorySlice(c.category, c.total, share_pct(c.total, total)) for c in ranked[:TOP_SLICES]]
    rest = ranked[TOP_SLICES:]
    if rest:
        other = money(sum((c.total for c in rest), ZERO))
        slices.append(CategorySlice(None, other, share_pct(other, total)))
    return tuple(slices)


def _reference_month(rows: Sequence[Row], today: dt.date) -> dt.date:
    """The latest month holding a transaction, up to today's month; the overall latest if all are later."""
    current = month_start(today)
    months = {month_start(r.date) for r in rows}
    reached = [m for m in months if m <= current]
    return max(reached) if reached else max(months)


def build_dashboard(rows: Sequence[Row], *, today: dt.date) -> Dashboard:
    """Everything the home page draws.

    The reference month is the latest month holding a transaction that is no later than today's
    month, so one future-dated row cannot take the page over. When every row is in the future it
    is the overall latest month.
    """
    if not rows:
        return EMPTY
    reference = _reference_month(rows, today)
    first = month_start(min(r.date for r in rows))
    month_rows = [r for r in rows if month_start(r.date) == reference]
    spent = expenses(month_rows)
    flagged = [r for r in spent if r.is_recurring]
    total = total_spend(spent)

    cashflow_window = month_range(max(first, add_months(reference, -(CASHFLOW_MONTHS - 1))), reference)
    cashflow = monthly_flows(rows, cashflow_window)
    trend = monthly_flows(rows, month_range(add_months(reference, -(TREND_MONTHS - 1)), reference))

    return Dashboard(
        reference_month=month_key(reference),
        total_spent=total,
        recurring_spent=total_spend(flagged),
        recurring_count=len(flagged),
        net_balance=cashflow[-1].net,
        average_cashflow=money(sum((m.net for m in cashflow), ZERO) / len(cashflow)),
        cashflow_months=len(cashflow),
        spending_by_category=_slices(month_rows, total),
        monthly_trend=tuple(TrendPoint(m.month, m.income, m.expenses) for m in trend),
    )
