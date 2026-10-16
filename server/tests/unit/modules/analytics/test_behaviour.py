"""Behaviour: weekdays, weekends, seasons, and which categories are steady."""

import datetime as dt
from decimal import Decimal

import pytest

from app.modules.analytics.domain.behaviour import MonthOfYear, WeekdaySpend, WeekPart, behaviour_analysis
from app.modules.analytics.domain.period import resolve_period
from tests.unit.modules.analytics.rows import row

pytestmark = pytest.mark.unit

# 2 March 2026 is a Monday; 2–15 March is 10 weekdays and 4 weekend days.
WEEK = [
    row("2026-03-02", "-20.00"),
    row("2026-03-03", "-10.00"),
    row("2026-03-07", "-40.00"),
    row("2026-03-08", "-20.00"),
    row("2026-03-09", "-10.00"),
    row("2026-03-14", "100.00", category="income"),
]
START, END = dt.date(2026, 3, 2), dt.date(2026, 3, 15)
TODAY = dt.date(2026, 10, 16)


def analyse(rows, **period):
    return behaviour_analysis(rows, resolve_period(rows, TODAY, **period))


def daily(first: str, last: str, amount: str = "-10.00"):
    day, end = dt.date.fromisoformat(first), dt.date.fromisoformat(last)
    rows = []
    while day <= end:
        rows.append(row(day.isoformat(), amount))
        day += dt.timedelta(days=1)
    return rows


def test_by_weekday_has_seven_days_from_monday():
    result = analyse(WEEK, date_from=START, date_to=END)
    days = result.by_weekday
    assert [d.name for d in days] == ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    assert days[0] == WeekdaySpend(0, "Monday", Decimal("30.00"), 2, Decimal("15.00"), 30.0, 2, Decimal("15.00"))
    assert days[2] == WeekdaySpend(2, "Wednesday", Decimal("0.00"), 0, Decimal("0.00"), 0.0, 2, Decimal("0.00"))
    assert days[5].share_pct == 40.0
    assert (result.date_from, result.date_to) == (START, END)


def test_weekend_per_day_divides_by_real_calendar_days():
    result = analyse(WEEK, date_from=START, date_to=END)
    assert result.weekday == WeekPart(10, Decimal("40.00"), Decimal("4.00"))
    assert result.weekend == WeekPart(4, Decimal("60.00"), Decimal("15.00"))
    assert result.weekend_bias_pct == 275.0


def test_weekday_occurrences_over_a_quarter():
    rows = daily("2026-07-01", "2026-09-30")  # 92 days from a Wednesday
    result = analyse(rows, months=3)
    assert [d.days for d in result.by_weekday] == [13, 13, 14, 13, 13, 13, 13]
    assert all(d.per_day == (d.total / d.days).quantize(Decimal("0.01")) for d in result.by_weekday)
    assert (result.date_from, result.date_to) == (dt.date(2026, 7, 1), dt.date(2026, 9, 30))


@pytest.mark.parametrize("start", [dt.date(2026, 3, 2) + dt.timedelta(days=i) for i in range(7)])
@pytest.mark.parametrize("length", [1, 6, 7, 8, 13, 200])
def test_weekday_and_weekend_days_match_a_day_by_day_count(start, length):
    end = start + dt.timedelta(days=length - 1)
    days = [start + dt.timedelta(days=i) for i in range(length)]
    result = analyse([row(start.isoformat(), "-1.00"), row(end.isoformat(), "-1.00")], date_from=start, date_to=end)
    assert result.weekend.days == sum(1 for d in days if d.weekday() >= 5)
    assert result.weekday.days == sum(1 for d in days if d.weekday() < 5)
    assert sum(d.days for d in result.by_weekday) == length


def test_weekend_bias_uses_unrounded_per_day_spend():
    rows = [row("2026-03-02", "-0.01"), row("2026-03-07", "-0.03")]  # per day 0.002 and 0.015
    result = analyse(rows, date_from=dt.date(2026, 3, 2), date_to=dt.date(2026, 3, 8))
    assert result.weekend_bias_pct == 650.0


def test_seasonality_uses_whole_months_only():
    rows = daily("2026-03-12", "2026-10-03")  # March and October are partial
    result = analyse(rows)
    march, april = result.seasonality[2], result.seasonality[3]
    assert march == MonthOfYear(3, Decimal("0.00"), None, 0)
    assert april == MonthOfYear(4, Decimal("300.00"), 98.36, 1)  # 300 over the mean of 300, 310, 300, 310, 310, 300
    assert result.seasonality[9].years == 0
    assert result.expense_change_pct == -3.23  # August 310 to September 300


def test_seasonality_counts_the_years_of_a_calendar_month():
    rows = [row("2025-01-01", "-100.00"), row("2026-01-10", "-300.00"), row("2026-02-10", "-80.00")]
    january = analyse(rows, months=24).seasonality[0]
    assert january.years == 2
    assert january.average_spend == Decimal("200.00")


def test_stability_judges_monthly_totals_from_the_first_month_with_spend():
    rows = [row("2026-08-05", "-5.00", category="shopping")]  # two whole months: too few
    for month in ("06", "07", "08", "09"):
        for day, amount in zip(("02", "05", "09", "12"), ("-5", "-20", "-125", "-150"), strict=True):
            rows.append(row(f"2026-{month}-{day}", amount, category="food_groceries"))
    rows += [
        row("2026-08-10", "-50.00", category="bars_restaurants"),
        row("2026-09-10", "-50.00", category="bars_restaurants"),
    ]
    result = analyse(sorted(rows, key=lambda r: r.date))
    assert [(s.category, s.count, s.months, s.cv, s.stability) for s in result.stability] == [
        ("food_groceries", 16, 4, 0.0, "stable")
    ]
    assert (result.stable_share_pct, result.moderate_share_pct, result.volatile_share_pct) == (100.0, 0.0, 0.0)


def test_stability_classes_follow_the_coefficient_of_variation():
    rows = []
    for month, amount in zip(("06", "07", "08", "09"), ("-10", "-50", "-10", "-50"), strict=True):
        rows.append(row(f"2026-{month}-10", amount, category="bars_restaurants"))
        rows.append(row(f"2026-{month}-11", "-100", category="food_groceries"))
    result = analyse(rows)
    assert [(s.category, s.stability) for s in result.stability] == [
        ("food_groceries", "stable"),
        ("bars_restaurants", "moderate"),
    ]


def test_month_over_month_expense_change_needs_two_whole_months():
    rows = [row("2026-08-01", "-100.00"), row("2026-09-10", "-150.00")]
    assert analyse(rows).expense_change_pct == 50.0
    assert analyse(WEEK, date_from=START, date_to=END).expense_change_pct is None  # one partial month


def test_empty_input():
    result = analyse([])
    assert result.weekday == WeekPart(0, Decimal("0.00"), Decimal("0.00"))
    assert result.weekend_bias_pct is None
    assert (result.date_from, result.date_to) == (None, None)
    assert len(result.by_weekday) == 7
    assert all(m.index is None and m.years == 0 for m in result.seasonality)
    assert result.stability == ()
