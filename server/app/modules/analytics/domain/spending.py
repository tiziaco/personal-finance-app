"""Spending: income, expenses and net per month and over the period, and the current month so far."""

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from app.modules.analytics.domain._aggregate import (
    ZERO,
    Row,
    add_months,
    average,
    expenses,
    group_by,
    incomes,
    money,
    month_end,
    month_key,
    month_start,
    pct_change,
    total_amount,
    total_spend,
)
from app.modules.analytics.domain.period import Period, PeriodMonth, calendar_month

ROLLING_MONTHS = 3


@dataclass(frozen=True)
class MonthFlow:
    """One month's income, expenses and net, with the change in expenses, a rolling average and the savings rate."""

    month: str
    income: Decimal
    expenses: Decimal
    net: Decimal
    expense_change_pct: Optional[float]
    partial: bool
    expenses_rolling_avg_3m: Optional[Decimal]
    savings_rate_pct: Optional[float]


@dataclass(frozen=True)
class LatestMonth:
    """The period's last whole month against the period's monthly averages."""

    month: str
    income: Decimal
    expenses: Decimal
    income_vs_average_pct: Optional[float]
    expenses_vs_average_pct: Optional[float]


@dataclass(frozen=True)
class MonthToDate:
    """The current month from day 1 to its last row, against the same days of the month before."""

    month: str
    through: dt.date
    income: Decimal
    expenses: Decimal
    net: Decimal
    previous_month: str
    previous_through: dt.date
    previous_income: Decimal
    previous_expenses: Decimal
    income_change_pct: Optional[float]
    expenses_change_pct: Optional[float]


@dataclass(frozen=True)
class SpendingSummary:
    """Totals, weighted monthly averages and the per-month series over a period, and month-to-date."""

    date_from: Optional[dt.date]
    date_to: Optional[dt.date]
    total_income: Decimal
    total_expenses: Decimal
    net: Decimal
    transaction_count: int
    average_income: Decimal
    average_expense: Decimal
    average_monthly_income: Optional[Decimal]
    average_monthly_expenses: Optional[Decimal]
    average_monthly_net: Optional[Decimal]
    burn_rate: Optional[Decimal]
    savings_rate_pct: Optional[float]
    months: tuple[MonthFlow, ...]
    latest_month: Optional[LatestMonth]
    month_to_date: Optional[MonthToDate]


def _savings_rate(net: Decimal, income: Decimal) -> Optional[float]:
    """Net as a percent of income; None when income is zero."""
    if income == 0:
        return None
    return round(float(net / income * 100), 2)


def _between(rows: Sequence[Row], first: dt.date, last: dt.date) -> list[Row]:
    return [r for r in rows if first <= r.date <= last]


def monthly_flows(rows: Sequence[Row], months: Sequence[PeriodMonth], *, today: dt.date) -> tuple[MonthFlow, ...]:
    """Income, expenses and net over each month's days, zero-filled.

    The change and the rolling average reach before the given months through calendar_month, and are None
    when a month they touch is partial or outside the data.
    """
    by_month = group_by(rows, lambda r: month_start(r.date))
    given = {m.start: m for m in months}
    whole_spend: dict[dt.date, Optional[Decimal]] = {}

    def spent(month: PeriodMonth) -> Decimal:
        return total_spend(expenses(_between(by_month.get(month.start, []), month.first_day, month.last_day)))

    def whole(start: dt.date) -> Optional[Decimal]:
        """The month's expenses when it is whole; None when partial or outside the data."""
        if start not in whole_spend:
            month = given.get(start) or calendar_month(start, rows, today)
            whole_spend[start] = None if month is None or month.partial else spent(month)
        return whole_spend[start]

    flows: list[MonthFlow] = []
    for month in months:
        days = _between(by_month.get(month.start, []), month.first_day, month.last_day)
        income, out = total_amount(incomes(days)), total_spend(expenses(days))
        net = money(income - out)
        previous, this = whole(add_months(month.start, -1)), whole(month.start)
        change = pct_change(previous, this) if previous is not None and this is not None else None
        window = [whole(add_months(month.start, -k)) for k in range(ROLLING_MONTHS)]
        rolling = None if None in window else money(sum(window, ZERO) / ROLLING_MONTHS)
        flows.append(
            MonthFlow(
                month_key(month.start), income, out, net, change, month.partial, rolling, _savings_rate(net, income)
            )
        )
    return tuple(flows)


def month_to_date(rows: Sequence[Row], today: dt.date) -> Optional[MonthToDate]:
    """Today's month up to its last row against the month before over the same day numbers; None without a row.

    The changes are None when the data starts after the month before's first day: its figures cover fewer days.
    """
    current = month_start(today)
    days = _between(rows, current, month_end(current))
    if not days:
        return None
    through = max(r.date for r in days)
    previous = add_months(current, -1)
    previous_through = previous.replace(day=min(through.day, month_end(previous).day))  # 31 March → 28 February
    before = _between(rows, previous, previous_through)
    income, out = total_amount(incomes(days)), total_spend(expenses(days))
    previous_income, previous_out = total_amount(incomes(before)), total_spend(expenses(before))
    seen = calendar_month(previous, rows, today)
    comparable = seen is not None and seen.first_day == previous
    return MonthToDate(
        month=month_key(current),
        through=through,
        income=income,
        expenses=out,
        net=money(income - out),
        previous_month=month_key(previous),
        previous_through=previous_through,
        previous_income=previous_income,
        previous_expenses=previous_out,
        income_change_pct=pct_change(previous_income, income) if comparable else None,
        expenses_change_pct=pct_change(previous_out, out) if comparable else None,
    )


def _latest_month(flows: Sequence[MonthFlow], monthly_in: Decimal, monthly_out: Decimal) -> Optional[LatestMonth]:
    whole = [f for f in flows if not f.partial]
    if not whole:
        return None
    last = whole[-1]
    return LatestMonth(
        last.month,
        last.income,
        last.expenses,
        pct_change(monthly_in, last.income),
        pct_change(monthly_out, last.expenses),
    )


def spending_summary(rows: Sequence[Row], period: Optional[Period], *, today: dt.date) -> SpendingSummary:
    """Totals, averages over the period's month weights and the per-month series; month-to-date regardless."""
    covered = period.rows(rows) if period else []
    money_in, money_out = incomes(covered), expenses(covered)
    total_in, total_out = total_amount(money_in), total_spend(money_out)
    weight = period.weight() if period else Decimal(0)
    # A part-month is never scaled up to a whole one: with no whole month there is no monthly average.
    averaged = bool(period and period.whole_months())
    monthly_in = money(total_in / weight) if averaged else None if period else ZERO
    monthly_out = money(total_out / weight) if averaged else None if period else ZERO
    monthly_net = money((total_in - total_out) / weight) if averaged else None if period else ZERO
    burn = money((total_out - total_in) / weight) if averaged else None if period else ZERO
    flows = monthly_flows(rows, period.months, today=today) if period else ()
    return SpendingSummary(
        date_from=period.first_day if period else None,
        date_to=period.last_day if period else None,
        total_income=total_in,
        total_expenses=total_out,
        net=money(total_in - total_out),
        transaction_count=len(money_in) + len(money_out),
        average_income=average(total_in, len(money_in)),
        average_expense=average(total_out, len(money_out)),
        average_monthly_income=monthly_in,
        average_monthly_expenses=monthly_out,
        average_monthly_net=monthly_net,
        burn_rate=burn,
        savings_rate_pct=_savings_rate(total_in - total_out, total_in),
        months=flows,
        latest_month=_latest_month(flows, monthly_in, monthly_out)
        if monthly_in is not None and monthly_out is not None
        else None,
        month_to_date=month_to_date(rows, today),
    )
