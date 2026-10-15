"""Spending: per-month flows, totals and averages over a zero-filled range."""

import datetime as dt
from decimal import Decimal

import pytest

from app.modules.analytics.domain.spending import MonthFlow, spending_summary
from tests.unit.modules.analytics.rows import row

pytestmark = pytest.mark.unit

# January and March have money; February has none; a zero amount on 15 March is ignored.
ROWS = [
    row("2026-01-05", "-100.00"),
    row("2026-01-20", "2000.00", category="salary"),
    row("2026-03-10", "-300.00"),
    row("2026-03-15", "0.00"),
    row("2026-03-28", "1000.00", category="salary"),
]


def test_months_are_zero_filled_and_growth_after_zero_is_none():
    result = spending_summary(ROWS)
    assert result.months == (
        MonthFlow("2026-01", Decimal("2000.00"), Decimal("100.00"), Decimal("1900.00"), None),
        MonthFlow("2026-02", Decimal("0.00"), Decimal("0.00"), Decimal("0.00"), -100.0),
        MonthFlow("2026-03", Decimal("1000.00"), Decimal("300.00"), Decimal("700.00"), None),
    )


def test_totals_and_averages():
    result = spending_summary(ROWS)
    assert (result.date_from, result.date_to) == (dt.date(2026, 1, 5), dt.date(2026, 3, 28))
    assert result.total_income == Decimal("3000.00")
    assert result.total_expenses == Decimal("400.00")
    assert result.net == Decimal("2600.00")
    assert result.transaction_count == 4  # the zero amount is not a transaction of either kind
    assert result.average_income == Decimal("1500.00")
    assert result.average_expense == Decimal("200.00")
    assert result.average_monthly_income == Decimal("1000.00")
    assert result.average_monthly_expenses == Decimal("133.33")
    assert result.burn_rate == Decimal("-866.67")


def test_given_bounds_widen_the_month_range():
    result = spending_summary(ROWS, date_from=dt.date(2025, 12, 1), date_to=dt.date(2026, 3, 31))
    assert [m.month for m in result.months] == ["2025-12", "2026-01", "2026-02", "2026-03"]
    assert result.average_monthly_income == Decimal("750.00")
    assert result.months[1].expense_change_pct is None  # December spent nothing


def test_empty_input_is_all_zero():
    result = spending_summary([])
    assert result.months == ()
    assert result.date_from is None and result.date_to is None
    assert result.total_expenses == Decimal("0.00")
    assert result.burn_rate == Decimal("0.00")
    assert result.transaction_count == 0
