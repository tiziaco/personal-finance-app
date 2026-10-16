"""Spending: per-month flows, weighted averages, the latest whole month and month-to-date (spec §4.1, §4.7)."""

import datetime as dt
from decimal import Decimal

import pytest

from app.modules.analytics.domain.period import resolve_period
from app.modules.analytics.domain.spending import LatestMonth, MonthFlow, MonthToDate, spending_summary
from tests.unit.modules.analytics.rows import row

pytestmark = pytest.mark.unit

TODAY = dt.date(2026, 10, 16)

# June spends 800; July and August spend 1000 and earn 2000; September spends 1300 (50 of it on the 1st) and
# earns 2000; October, the current month, spends 100 on the 2nd.
ROWS = [
    row("2026-06-01", "-800.00"),
    row("2026-07-10", "-1000.00"),
    row("2026-07-25", "2000.00", category="salary"),
    row("2026-08-10", "-1000.00"),
    row("2026-08-25", "2000.00", category="salary"),
    row("2026-09-01", "-50.00"),
    row("2026-09-10", "-1250.00"),
    row("2026-09-25", "2000.00", category="salary"),
    row("2026-10-02", "-100.00"),
]


def summary(rows=ROWS, today=TODAY, **request):
    return spending_summary(rows, resolve_period(rows, today, **request), today=today)


def test_three_finished_months_totals_and_averages():
    result = summary(months=3)
    assert (result.date_from, result.date_to) == (dt.date(2026, 7, 1), dt.date(2026, 9, 30))
    assert result.total_income == Decimal("6000.00")
    assert result.total_expenses == Decimal("3300.00")
    assert result.net == Decimal("2700.00")
    assert result.transaction_count == 7
    assert result.average_income == Decimal("2000.00")  # per transaction
    assert result.average_expense == Decimal("825.00")
    assert result.average_monthly_income == Decimal("2000.00")
    assert result.average_monthly_expenses == Decimal("1100.00")
    assert result.average_monthly_net == Decimal("900.00")
    assert result.burn_rate == Decimal("-900.00")
    assert result.savings_rate_pct == 45.0


def test_month_series_reaches_before_the_period_for_change_and_rolling_average():
    july, august, september = summary(months=3).months
    assert july == MonthFlow(
        "2026-07", Decimal("2000.00"), Decimal("1000.00"), Decimal("1000.00"), 25.0, False, None, 50.0
    )  # change against June, outside the period; no rolling average, May is before the data
    assert august.expenses_rolling_avg_3m == Decimal("933.33")  # (800 + 1000 + 1000) ÷ 3
    assert august.expense_change_pct == 0.0
    assert september == MonthFlow(
        "2026-09", Decimal("2000.00"), Decimal("1300.00"), Decimal("700.00"), 30.0, False, Decimal("1100.00"), 35.0
    )


def test_latest_month_compares_with_the_period_average():
    assert summary(months=3).latest_month == LatestMonth("2026-09", Decimal("2000.00"), Decimal("1300.00"), 0.0, 18.18)


def test_month_to_date_against_the_same_days_of_the_month_before():
    assert summary(months=3).month_to_date == MonthToDate(
        "2026-10",
        dt.date(2026, 10, 2),
        Decimal("0.00"),
        Decimal("100.00"),
        "2026-09",
        Decimal("0.00"),
        Decimal("50.00"),
        None,
        100.0,
    )


def test_a_bound_cutting_a_month_weights_it_by_the_days_covered():
    result = summary(date_from=dt.date(2026, 8, 16), date_to=dt.date(2026, 9, 30))
    august, september = result.months
    assert august.partial and not september.partial
    assert (result.total_income, result.total_expenses) == (Decimal("4000.00"), Decimal("1300.00"))
    assert august.expenses == Decimal("0.00")  # the 10 August expense is before the bound
    assert result.average_monthly_income == Decimal("2638.30")  # 4000 ÷ 47/31
    assert august.expense_change_pct is None and august.expenses_rolling_avg_3m is None
    assert september.expense_change_pct is None  # August is partial
    assert september.expenses_rolling_avg_3m is None
    assert result.latest_month is not None and result.latest_month.month == "2026-09"


def test_only_this_months_data_is_one_partial_month():
    # Review Focus 3: one usable row.
    result = summary(rows=[row("2026-10-02", "-100.00")])
    (october,) = result.months
    assert october.partial and october.month == "2026-10"
    assert (result.date_from, result.date_to) == (dt.date(2026, 10, 1), dt.date(2026, 10, 2))
    assert result.latest_month is None
    assert result.average_monthly_expenses == Decimal("1550.00")  # 100 ÷ 2/31
    assert result.average_monthly_income == Decimal("0.00")
    assert result.burn_rate == Decimal("1550.00")
    assert result.savings_rate_pct is None
    assert october.savings_rate_pct is None and october.expense_change_pct is None
    assert result.month_to_date is not None and result.month_to_date.expenses_change_pct is None


def test_month_to_date_on_the_31st_clamps_to_a_shorter_month():
    # Review Focus 2.
    today = dt.date(2026, 3, 31)
    result = summary(rows=[row("2026-02-28", "-10.00"), row("2026-03-31", "-20.00")], today=today)
    mtd = result.month_to_date
    assert (mtd.month, mtd.through) == ("2026-03", dt.date(2026, 3, 31))
    assert (mtd.previous_month, mtd.previous_expenses) == ("2026-02", Decimal("10.00"))
    assert mtd.expenses_change_pct == 100.0


def test_month_to_date_is_none_without_a_row_this_month():
    assert summary(rows=ROWS[:-1]).month_to_date is None


def test_month_steps_cross_the_year_boundary():
    # Review Focus 1: October 2025's change compares with September 2025, before the period.
    rows = [row("2025-09-05", "-100.00"), row("2025-10-05", "-150.00")]
    rows += [row("2025-11-05", "-150.00"), row("2025-12-05", "-200.00")]
    result = summary(rows=rows, today=dt.date(2026, 1, 20), months=3)
    october, november, december = result.months
    assert october.month == "2025-10" and october.expense_change_pct == 50.0
    assert october.expenses_rolling_avg_3m is None  # August 2025 is before the data
    assert november.expenses_rolling_avg_3m == Decimal("133.33")
    assert december.expenses_rolling_avg_3m == Decimal("166.67")
    assert result.latest_month.month == "2025-12"


def test_a_gap_month_is_zero_filled_and_a_change_after_it_is_none():
    rows = [row("2026-07-05", "-100.00"), row("2026-09-05", "-300.00")]
    result = summary(rows=rows)
    assert [(m.month, m.expenses) for m in result.months] == [
        ("2026-07", Decimal("100.00")),
        ("2026-08", Decimal("0.00")),
        ("2026-09", Decimal("300.00")),
    ]
    assert result.months[1].expense_change_pct == -100.0
    assert result.months[2].expense_change_pct is None  # August spent nothing
    assert result.months[2].expenses_rolling_avg_3m == Decimal("133.33")


def test_a_zero_amount_is_neither_income_nor_expense():
    rows = [row("2026-09-05", "-100.00"), row("2026-09-06", "0.00")]
    assert summary(rows=rows).transaction_count == 1


def test_empty_input_is_all_zero():
    result = spending_summary([], None, today=TODAY)
    assert result.months == ()
    assert result.date_from is None and result.date_to is None
    assert (result.total_income, result.total_expenses, result.net) == (Decimal("0.00"),) * 3
    assert result.average_monthly_net == Decimal("0.00")
    assert result.burn_rate == Decimal("0.00")
    assert result.savings_rate_pct is None
    assert result.transaction_count == 0
    assert result.latest_month is None and result.month_to_date is None
