"""Spending: income, expenses and net per month and over the range."""

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from app.modules.analytics.domain._aggregate import (
    ZERO,
    Row,
    average,
    expenses,
    incomes,
    money,
    month_key,
    month_range,
    monthly_totals,
    pct_change,
    span,
    spend,
    total_amount,
    total_spend,
)


@dataclass(frozen=True)
class MonthFlow:
    """One month's income, expenses and net, with expense change against the month before."""

    month: str
    income: Decimal
    expenses: Decimal
    net: Decimal
    expense_change_pct: Optional[float]


@dataclass(frozen=True)
class SpendingSummary:
    """Totals, averages and the per-month series over a range."""

    date_from: Optional[dt.date]
    date_to: Optional[dt.date]
    total_income: Decimal
    total_expenses: Decimal
    net: Decimal
    transaction_count: int
    average_income: Decimal
    average_expense: Decimal
    average_monthly_income: Decimal
    average_monthly_expenses: Decimal
    burn_rate: Decimal
    months: tuple[MonthFlow, ...]


def monthly_flows(rows: Sequence[Row], months: Sequence[dt.date]) -> tuple[MonthFlow, ...]:
    """Income, expenses and net for each month, zero-filled; expense change against the month before."""
    income = monthly_totals(incomes(rows), months, lambda r: r.amount)
    spent = monthly_totals(expenses(rows), months, spend)
    flows: list[MonthFlow] = []
    for i, month in enumerate(months):
        change = pct_change(spent[i - 1], spent[i]) if i > 0 else None
        flows.append(MonthFlow(month_key(month), income[i], spent[i], money(income[i] - spent[i]), change))
    return tuple(flows)


def spending_summary(
    rows: Sequence[Row], date_from: Optional[dt.date] = None, date_to: Optional[dt.date] = None
) -> SpendingSummary:
    """Totals, averages and the per-month series over the range (the bounds, else the data's span)."""
    covered = span(rows, date_from, date_to)
    months = month_range(*covered) if covered else []
    money_in, money_out = incomes(rows), expenses(rows)
    total_in, total_out = total_amount(money_in), total_spend(money_out)
    monthly_in = average(total_in, len(months))
    monthly_out = average(total_out, len(months))
    return SpendingSummary(
        date_from=covered[0] if covered else None,
        date_to=covered[1] if covered else None,
        total_income=total_in,
        total_expenses=total_out,
        net=money(total_in - total_out),
        transaction_count=len(money_in) + len(money_out),
        average_income=average(total_in, len(money_in)),
        average_expense=average(total_out, len(money_out)),
        average_monthly_income=monthly_in,
        average_monthly_expenses=monthly_out,
        burn_rate=money(monthly_out - monthly_in) if months else ZERO,
        months=monthly_flows(rows, months),
    )
