"""Behaviour: weekdays, weekends, seasons, and which categories are steady."""

import datetime as dt
from decimal import Decimal

import pytest

from app.modules.analytics.domain.behaviour import MonthOfYear, WeekdaySpend, WeekPart, behaviour_analysis
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


def test_by_weekday_has_seven_days_from_monday():
    days = behaviour_analysis(WEEK, START, END).by_weekday
    assert [d.name for d in days] == ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    assert days[0] == WeekdaySpend(0, "Monday", Decimal("30.00"), 2, Decimal("15.00"), 30.0)
    assert days[2] == WeekdaySpend(2, "Wednesday", Decimal("0.00"), 0, Decimal("0.00"), 0.0)
    assert days[5].share_pct == 40.0


def test_weekend_per_day_divides_by_real_calendar_days():
    result = behaviour_analysis(WEEK, START, END)
    assert result.weekday == WeekPart(10, Decimal("40.00"), Decimal("4.00"))
    assert result.weekend == WeekPart(4, Decimal("60.00"), Decimal("15.00"))
    assert result.weekend_bias_pct == 275.0


def test_stability_classes_need_five_expenses():
    rows = [row(f"2026-03-0{d}", "-10.00", category="food_groceries") for d in range(1, 6)]
    rows += [
        row(f"2026-03-0{d}", a, category="bars_restaurants")
        for d, a in zip(range(1, 6), ["-10", "-50", "-10", "-50", "-10"], strict=True)
    ]
    rows += [row(f"2026-03-0{d}", "-99.00", category="shopping") for d in range(1, 5)]  # four: unclassified
    result = behaviour_analysis(sorted(rows, key=lambda r: r.date))
    assert [(s.category, s.cv, s.stability) for s in result.stability] == [
        ("food_groceries", 0.0, "stable"),
        ("bars_restaurants", 0.7537, "volatile"),
    ]
    assert (result.stable_share_pct, result.moderate_share_pct, result.volatile_share_pct) == (27.78, 0.0, 72.22)


def test_seasonality_averages_each_calendar_month_across_years():
    rows = [row("2025-01-10", "-100.00"), row("2026-01-10", "-300.00")]
    season = behaviour_analysis(rows).seasonality
    assert len(season) == 12
    assert season[0] == MonthOfYear(1, Decimal("200.00"), 650.0)  # 400 over 13 months → mean 30.77
    assert season[1] == MonthOfYear(2, Decimal("0.00"), 0.0)


def test_month_over_month_expense_change():
    rows = [row("2026-02-10", "-100.00"), row("2026-03-10", "-150.00")]
    assert behaviour_analysis(rows).expense_change_pct == 50.0
    assert behaviour_analysis(WEEK, START, END).expense_change_pct is None  # one month


def test_empty_input():
    result = behaviour_analysis([])
    assert result.weekday == WeekPart(0, Decimal("0.00"), Decimal("0.00"))
    assert result.weekend_bias_pct is None
    assert all(m.index is None for m in result.seasonality)
    assert result.stability == ()
