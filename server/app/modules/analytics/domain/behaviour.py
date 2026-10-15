"""Behaviour: spending by weekday and season, and how steady each category is."""

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from statistics import mean
from typing import Literal, Optional

from app.modules.analytics.domain._aggregate import (
    ZERO,
    Row,
    average,
    cv,
    expenses,
    group_by,
    money,
    month_range,
    monthly_totals,
    pct_change,
    share_pct,
    span,
    spend,
    total_spend,
)

WEEKDAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
WEEKEND = (5, 6)
STABILITY_MIN_EXPENSES = 5
STABLE_BELOW = 0.3
MODERATE_BELOW = 0.7

Stability = Literal["stable", "moderate", "volatile"]


@dataclass(frozen=True)
class WeekdaySpend:
    """Spend on one day of the week: its total, count, average charge and share of all spend."""

    weekday: int
    name: str
    total: Decimal
    count: int
    average: Decimal
    share_pct: float


@dataclass(frozen=True)
class WeekPart:
    """Weekdays or weekend days: how many calendar days, their spend, and the average per day."""

    days: int
    total: Decimal
    per_day: Decimal


@dataclass(frozen=True)
class MonthOfYear:
    """A calendar month averaged across the years covered, and its index against the mean month."""

    month: int
    average_spend: Decimal
    index: Optional[float]


@dataclass(frozen=True)
class CategoryStability:
    """A category with enough expenses to judge, its coefficient of variation and its class."""

    category: str
    count: int
    cv: float
    stability: Stability


@dataclass(frozen=True)
class Behaviour:
    """Weekday and weekend spend, seasonality, category stability and the last month-over-month change."""

    by_weekday: tuple[WeekdaySpend, ...]
    weekday: WeekPart
    weekend: WeekPart
    weekend_bias_pct: Optional[float]
    seasonality: tuple[MonthOfYear, ...]
    stability: tuple[CategoryStability, ...]
    stable_share_pct: float
    moderate_share_pct: float
    volatile_share_pct: float
    expense_change_pct: Optional[float]


def _week_part(spent: Sequence[Row], covered: Optional[tuple[dt.date, dt.date]], weekend: bool) -> WeekPart:
    rows = [r for r in spent if (r.date.weekday() in WEEKEND) == weekend]
    days = 0
    if covered:
        length = (covered[1] - covered[0]).days + 1
        weeks, extra = divmod(length, 7)  # whole weeks hold two weekend days; count the rest one by one
        weekend_days = weeks * len(WEEKEND) + sum(1 for i in range(extra) if (covered[0].weekday() + i) % 7 in WEEKEND)
        days = weekend_days if weekend else length - weekend_days
    total = total_spend(rows)
    return WeekPart(days, total, average(total, days))


def _seasonality(spent: Sequence[Row], months: Sequence[dt.date]) -> tuple[MonthOfYear, ...]:
    totals = monthly_totals(spent, months, spend)
    overall = mean(totals) if totals else ZERO
    result: list[MonthOfYear] = []
    for calendar_month in range(1, 13):
        present = [t for m, t in zip(months, totals, strict=True) if m.month == calendar_month]
        if not present:
            result.append(MonthOfYear(calendar_month, ZERO, None))
            continue
        avg = money(sum(present, ZERO) / len(present))
        index = round(float(sum(present, ZERO) / len(present) / overall * 100), 2) if overall else None
        result.append(MonthOfYear(calendar_month, avg, index))
    return tuple(result)


def _stability(spent: Sequence[Row]) -> list[CategoryStability]:
    classified: list[CategoryStability] = []
    for category, group in group_by(spent, lambda r: r.category).items():
        if len(group) < STABILITY_MIN_EXPENSES:
            continue
        value = cv([spend(r) for r in group]) or 0.0
        label: Stability = "stable" if value < STABLE_BELOW else "moderate" if value < MODERATE_BELOW else "volatile"
        classified.append(CategoryStability(category, len(group), value, label))
    return sorted(classified, key=lambda s: (s.cv, s.category))


def behaviour_analysis(
    rows: Sequence[Row], date_from: Optional[dt.date] = None, date_to: Optional[dt.date] = None
) -> Behaviour:
    """Weekday and weekend spend, seasonality, category stability and the last month-over-month change."""
    spent = expenses(rows)
    whole = total_spend(spent)
    covered = span(rows, date_from, date_to)
    months = month_range(*covered) if covered else []

    by_day = group_by(spent, lambda r: r.date.weekday())
    weekdays = tuple(
        WeekdaySpend(
            day,
            WEEKDAY_NAMES[day],
            total_spend(by_day.get(day, [])),
            len(by_day.get(day, [])),
            average(total_spend(by_day.get(day, [])), len(by_day.get(day, []))),
            share_pct(total_spend(by_day.get(day, [])), whole),
        )
        for day in range(7)
    )
    weekday, weekend = _week_part(spent, covered, False), _week_part(spent, covered, True)
    bias = pct_change(weekday.per_day, weekend.per_day)

    stability = _stability(spent)
    by_class = {
        label: total_spend(r for s in stability if s.stability == label for r in spent if r.category == s.category)
        for label in ("stable", "moderate", "volatile")
    }
    classified = sum(by_class.values(), ZERO)

    totals = monthly_totals(spent, months, spend)
    change = pct_change(totals[-2], totals[-1]) if len(totals) >= 2 else None

    return Behaviour(
        by_weekday=weekdays,
        weekday=weekday,
        weekend=weekend,
        weekend_bias_pct=bias,
        seasonality=_seasonality(spent, months),
        stability=tuple(stability),
        stable_share_pct=share_pct(by_class["stable"], classified),
        moderate_share_pct=share_pct(by_class["moderate"], classified),
        volatile_share_pct=share_pct(by_class["volatile"], classified),
        expense_change_pct=change,
    )
