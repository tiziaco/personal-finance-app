"""Categories: ranked spend against the previous period, and growth between the period's halves."""

import datetime as dt
from decimal import Decimal

import pytest

from app.modules.analytics.domain.categories import CategorySpend, CategoryTrend, category_breakdown, category_spend
from app.modules.analytics.domain.period import resolve_period
from tests.unit.modules.analytics.rows import row

pytestmark = pytest.mark.unit

TODAY = dt.date(2026, 10, 16)

ROWS = [
    row("2026-06-05", "-200.00", category="groceries"),
    row("2026-07-05", "-200.00", category="groceries"),
    row("2026-08-05", "-300.00", category="groceries"),
    row("2026-09-05", "-300.00", category="groceries"),
    row("2026-06-05", "-100.00", category="dining"),
    row("2026-07-05", "-100.00", category="dining"),
    row("2026-08-05", "-40.00", category="gym"),
    row("2026-09-05", "-40.00", category="gym"),
    row("2026-09-06", "3000.00", category="salary"),  # income: never a category's spend
]


def breakdown(months: int, rows=ROWS, top_n: int = 10):
    period = resolve_period(rows, TODAY, months=months)
    return category_breakdown(rows, period, top_n, today=TODAY)


def test_growth_between_the_halves():
    result = breakdown(4)
    assert result.top_growing == (
        CategoryTrend("groceries", Decimal("200.00"), Decimal("300.00"), Decimal("100.00"), 50.0),
        CategoryTrend("gym", Decimal("0.00"), Decimal("40.00"), Decimal("40.00"), None),
    )
    assert result.top_declining == (
        CategoryTrend("dining", Decimal("100.00"), Decimal("0.00"), Decimal("-100.00"), -100.0),
    )


def test_an_odd_count_leaves_the_middle_month_out():
    result = breakdown(3)  # Jul | Aug | Sep: July against September
    groceries = next(t for t in result.top_growing if t.category == "groceries")
    assert (groceries.earlier_monthly_average, groceries.later_monthly_average) == (
        Decimal("200.00"),
        Decimal("300.00"),
    )


def test_one_whole_month_has_no_halves():
    result = breakdown(1)
    assert result.top_growing == () and result.top_declining == ()


def test_a_partial_month_is_in_neither_half():
    rows = [*ROWS, row("2026-10-02", "-900.00", category="groceries")]
    period = resolve_period(rows, TODAY, date_from=dt.date(2026, 8, 1), date_to=dt.date(2026, 10, 31))
    assert [m.partial for m in period.months] == [False, False, True]
    result = category_breakdown(rows, period, today=TODAY)
    assert result.top_growing == ()  # August 300 against September 300, October left out


def test_ties_in_change_amount_order_by_slug():
    rows = [row("2026-08-05", "-10.00", category=c) for c in ("b", "a")] + [
        row("2026-09-05", "-30.00", category=c) for c in ("b", "a")
    ]
    result = breakdown(2, rows)
    assert [t.category for t in result.top_growing] == ["a", "b"]


def test_change_against_the_previous_period():
    result = breakdown(2)  # Aug-Sep against Jun-Jul
    by_name = {i.category: i for i in result.top_categories}
    assert (by_name["groceries"].total, by_name["groceries"].previous_total, by_name["groceries"].change_pct) == (
        Decimal("600.00"),
        Decimal("400.00"),
        50.0,
    )
    assert (by_name["gym"].previous_total, by_name["gym"].change_pct) == (Decimal("0.00"), None)
    assert "dining" not in by_name  # only in the previous period
    assert (result.previous_date_from, result.previous_date_to) == (dt.date(2026, 6, 1), dt.date(2026, 7, 31))
    assert {i.category: i.previous_total for i in result.by_frequency} == {
        "groceries": Decimal("400.00"),
        "gym": Decimal("0.00"),
    }


def test_no_previous_period_leaves_the_previous_figures_null():
    result = breakdown(4)  # Feb-May holds no rows
    assert (result.previous_date_from, result.previous_date_to) == (None, None)
    assert all(i.previous_total is None and i.change_pct is None for i in result.top_categories)


def test_a_previous_period_shorter_than_the_period_leaves_the_previous_figures_null():
    rows = [row(f"2026-{m:02d}-05", "-100.00", category="groceries") for m in range(5, 10)]
    result = breakdown(3, rows=rows)  # Jul-Sep; April-June would hold only May and June
    assert (result.previous_date_from, result.previous_date_to) == (None, None)
    (groceries,) = result.top_categories
    assert (groceries.previous_total, groceries.change_pct) == (None, None)


def test_the_period_echo_and_total():
    result = breakdown(2)
    assert (result.date_from, result.date_to) == (dt.date(2026, 8, 1), dt.date(2026, 9, 30))
    assert result.total_expenses == Decimal("680.00")


def test_top_n_cuts_both_rankings():
    result = breakdown(2, top_n=1)
    assert [i.category for i in result.top_categories] == ["groceries"]
    assert len(result.by_frequency) == 1


def test_category_spend_carries_no_previous_figures():
    assert category_spend(ROWS)[0] == CategorySpend("groceries", Decimal("1000.00"), 4, Decimal("250.00"), 78.12)


def test_empty_period():
    result = category_breakdown([], None, today=TODAY)
    assert (result.date_from, result.total_expenses, result.top_categories) == (None, Decimal("0.00"), ())
