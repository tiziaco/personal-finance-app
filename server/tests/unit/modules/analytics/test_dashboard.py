"""The home page's figures, all anchored to the latest month with data (spec D1, D2)."""

import datetime as dt
from decimal import Decimal

import pytest

from app.modules.analytics.domain.dashboard import CategorySlice, TrendPoint, build_dashboard
from tests.unit.modules.analytics.rows import row

pytestmark = pytest.mark.unit

TODAY = dt.date(2026, 10, 16)

ROWS = [
    row("2026-07-10", "-100.00", category="food_groceries"),
    row("2026-07-25", "2000.00", category="salary"),
    row("2026-08-05", "-900.00", merchant="Landlord", category="household_utilities", recurring=True),
    row("2026-08-10", "2000.00", category="salary"),
    row("2026-09-01", "-900.00", merchant="Landlord", category="household_utilities", recurring=True),
    row("2026-09-03", "-15.00", merchant="Netflix", category="leisure_entertainment", recurring=True),
    row("2026-09-05", "-200.00", category="food_groceries"),
    row("2026-09-06", "-100.00", category="bars_restaurants"),
    row("2026-09-07", "-80.00", category="transportation"),
    row("2026-09-08", "-60.00", category="shopping"),
    row("2026-09-09", "-40.00", category="healthcare_drug_stores"),
    row("2026-09-25", "2100.00", category="salary"),
]


def test_cards_read_the_latest_month_with_data():
    d = build_dashboard(ROWS, today=TODAY)
    assert d.reference_month == "2026-09"
    assert d.total_spent == Decimal("1395.00")
    assert (d.recurring_spent, d.recurring_count) == (Decimal("915.00"), 2)
    assert d.net_balance == Decimal("705.00")
    assert (d.average_cashflow, d.cashflow_months) == (Decimal("1235.00"), 3)  # (1900 + 1100 + 705) ÷ 3


def test_top_five_categories_and_other_sum_to_total_spent():
    d = build_dashboard(ROWS, today=TODAY)
    assert d.spending_by_category == (
        CategorySlice("household_utilities", Decimal("900.00"), 64.52),
        CategorySlice("food_groceries", Decimal("200.00"), 14.34),
        CategorySlice("bars_restaurants", Decimal("100.00"), 7.17),
        CategorySlice("transportation", Decimal("80.00"), 5.73),
        CategorySlice("shopping", Decimal("60.00"), 4.3),
        CategorySlice(None, Decimal("55.00"), 3.94),
    )
    assert sum(s.amount for s in d.spending_by_category) == d.total_spent


def test_trend_stops_at_the_first_month_of_data():
    assert build_dashboard(ROWS, today=TODAY).monthly_trend == (
        TrendPoint("2026-07", Decimal("2000.00"), Decimal("100.00")),
        TrendPoint("2026-08", Decimal("2000.00"), Decimal("900.00")),
        TrendPoint("2026-09", Decimal("2100.00"), Decimal("1395.00")),
    )


def test_trend_is_six_months_with_a_longer_history():
    rows = [row("2026-03-10", "-10.00"), *ROWS]
    assert [p.month for p in build_dashboard(rows, today=TODAY).monthly_trend] == [
        "2026-03",
        "2026-04",
        "2026-05",
        "2026-06",
        "2026-07",
        "2026-08",
        "2026-09",
    ][-6:]


def test_a_single_month_of_data_has_a_single_trend_point():
    d = build_dashboard([row("2026-09-01", "-40.00")], today=TODAY)
    assert [p.month for p in d.monthly_trend] == ["2026-09"]


def test_one_month_of_data_averages_over_one_month():
    d = build_dashboard([row("2026-09-01", "-40.00"), row("2026-09-02", "100.00", category="salary")], today=TODAY)
    assert (d.average_cashflow, d.cashflow_months) == (Decimal("60.00"), 1)


def test_a_gap_month_inside_the_window_counts_as_zero():
    d = build_dashboard([row("2026-06-15", "500.00", category="salary"), row("2026-09-01", "-30.00")], today=TODAY)
    assert d.cashflow_months == 3  # July, August (empty) and September; June is outside the window
    assert d.average_cashflow == Decimal("-10.00")


def test_five_or_fewer_categories_have_no_other_slice():
    d = build_dashboard([row("2026-09-01", "-40.00", category="shopping")], today=TODAY)
    assert d.spending_by_category == (CategorySlice("shopping", Decimal("40.00"), 100.0),)


def test_no_transactions():
    d = build_dashboard([], today=TODAY)
    assert d.reference_month is None
    assert d.total_spent == Decimal("0.00") and d.average_cashflow == Decimal("0.00")
    assert d.cashflow_months == 0
    assert d.spending_by_category == () and d.monthly_trend == ()


def test_the_reference_month_is_the_latest_finished_month_with_month_to_date_beside_it():
    d = build_dashboard([*ROWS, row("2026-10-02", "-50.00")], today=TODAY)
    assert (d.reference_month, d.reference_partial) == ("2026-09", False)
    assert d.total_spent == Decimal("1395.00")
    assert d.month_to_date is not None and d.month_to_date.month == "2026-10"


def test_without_a_row_this_month_there_is_no_month_to_date():
    d = build_dashboard(ROWS, today=TODAY)
    assert d.reference_partial is False
    assert d.month_to_date is None


def test_a_user_whose_only_row_is_this_month_sees_it_as_partial():
    d = build_dashboard([row("2026-10-02", "-50.00")], today=TODAY)
    assert (d.reference_month, d.reference_partial) == ("2026-10", True)
    assert d.total_spent == Decimal("50.00")
    assert [p.month for p in d.monthly_trend] == ["2026-10"]
    assert (d.cashflow_months, d.net_balance) == (1, Decimal("-50.00"))
    assert d.month_to_date is not None and d.month_to_date.month == "2026-10"


def test_a_future_row_does_not_take_over_the_reference_month():
    d = build_dashboard([*ROWS, row("2027-01-05", "-777.00")], today=TODAY)
    assert d.reference_month == "2026-09"
    assert d.total_spent == Decimal("1395.00")
    assert d.monthly_trend[-1] == TrendPoint("2026-09", Decimal("2100.00"), Decimal("1395.00"))


def test_only_future_rows_leave_the_dashboard_empty():
    d = build_dashboard([row("2027-01-05", "-10.00"), row("9999-12-31", "-20.00")], today=TODAY)
    assert d.reference_month is None
    assert d.monthly_trend == () and d.month_to_date is None
