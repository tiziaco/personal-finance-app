"""Behaviour: spending by weekday and season, and how steady each category is."""

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, Optional

from app.modules.analytics.domain._aggregate import (
    ZERO,
    Row,
    average,
    cv,
    expenses,
    group_by,
    money,
    month_start,
    monthly_totals,
    pct_change,
    share_pct,
    spend,
    total_spend,
)
from app.modules.analytics.domain.period import Period

WEEKDAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
WEEKEND = (5, 6)
STABILITY_MIN_MONTHS = 3
STABLE_BELOW = 0.3
MODERATE_BELOW = 0.7

Stability = Literal["stable", "moderate", "volatile"]


@dataclass(frozen=True)
class WeekdaySpend:
    """Spend on one day of the week: total, count, average charge, share of all spend and spend per occurrence."""

    weekday: int
    name: str
    total: Decimal
    count: int
    average: Decimal
    share_pct: float
    days: int
    per_day: Decimal


@dataclass(frozen=True)
class WeekPart:
    """Weekdays or weekend days: how many calendar days, their spend, and the average per day."""

    days: int
    total: Decimal
    per_day: Decimal


@dataclass(frozen=True)
class MonthOfYear:
    """A calendar month averaged over the whole months of it in the period, and its index against the mean month."""

    month: int
    average_spend: Decimal
    index: Optional[float]
    years: int


@dataclass(frozen=True)
class CategoryStability:
    """A category with enough whole months to judge, its coefficient of variation and its class."""

    category: str
    count: int
    months: int
    cv: float
    stability: Stability


@dataclass(frozen=True)
class Behaviour:
    """Weekday and weekend spend, seasonality, category stability and the last month-over-month change."""

    date_from: Optional[dt.date]
    date_to: Optional[dt.date]
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


def _days_by_weekday(period: Optional[Period]) -> list[int]:
    """How many times each weekday occurs from the period's first to its last day."""
    if period is None:
        return [0] * 7
    length = (period.last_day - period.first_day).days + 1
    weeks, extra = divmod(length, 7)
    first = period.first_day.weekday()
    return [weeks + (1 if (day - first) % 7 < extra else 0) for day in range(7)]


def _per_day(total: Decimal, days: int) -> Decimal:
    return total / days if days else ZERO


def _seasonality(spent: Sequence[Row], whole: Sequence[dt.date]) -> tuple[MonthOfYear, ...]:
    totals = monthly_totals(spent, whole, spend)
    overall = sum(totals, ZERO) / len(totals) if totals else ZERO
    result: list[MonthOfYear] = []
    for calendar_month in range(1, 13):
        present = [t for m, t in zip(whole, totals, strict=True) if m.month == calendar_month]
        if not present:
            result.append(MonthOfYear(calendar_month, ZERO, None, 0))
            continue
        mean_spend = sum(present, ZERO) / len(present)
        index = round(float(mean_spend / overall * 100), 2) if overall else None
        result.append(MonthOfYear(calendar_month, money(mean_spend), index, len(present)))
    return tuple(result)


def _stability(spent: Sequence[Row], whole: Sequence[dt.date]) -> list[tuple[CategoryStability, Decimal]]:
    """Each classified category with its spend over the months judged."""
    classified: list[tuple[CategoryStability, Decimal]] = []
    for category, group in group_by(spent, lambda r: r.category).items():
        totals = monthly_totals(group, whole, spend)
        first = next((i for i, t in enumerate(totals) if t > 0), None)
        if first is None or len(totals) - first < STABILITY_MIN_MONTHS:
            continue
        judged = totals[first:]
        start = whole[first]
        kept = [r for r in group if r.date >= start and month_start(r.date) in set(whole)]
        value = cv(judged) or 0.0
        label: Stability = "stable" if value < STABLE_BELOW else "moderate" if value < MODERATE_BELOW else "volatile"
        classified.append((CategoryStability(category, len(kept), len(judged), value, label), sum(judged, ZERO)))
    return sorted(classified, key=lambda c: (c[0].cv, c[0].category))


def behaviour_analysis(rows: Sequence[Row], period: Optional[Period]) -> Behaviour:
    """Weekday and weekend spend over the period; seasonality, stability and change over its whole months."""
    spent = expenses(period.rows(rows)) if period else []
    total = total_spend(spent)
    whole = [m.start for m in period.whole_months()] if period else []

    by_day = group_by(spent, lambda r: r.date.weekday())
    occurrences = _days_by_weekday(period)
    weekdays = tuple(
        WeekdaySpend(
            day,
            WEEKDAY_NAMES[day],
            total_spend(by_day.get(day, [])),
            len(by_day.get(day, [])),
            average(total_spend(by_day.get(day, [])), len(by_day.get(day, []))),
            share_pct(total_spend(by_day.get(day, [])), total),
            occurrences[day],
            money(_per_day(total_spend(by_day.get(day, [])), occurrences[day])),
        )
        for day in range(7)
    )
    parts: list[WeekPart] = []
    unrounded: list[Decimal] = []
    for is_weekend in (False, True):
        days = sum(occurrences[d] for d in range(7) if (d in WEEKEND) == is_weekend)
        part_total = total_spend(r for r in spent if (r.date.weekday() in WEEKEND) == is_weekend)
        unrounded.append(_per_day(part_total, days))
        parts.append(WeekPart(days, part_total, money(unrounded[-1])))
    weekday, weekend = parts

    classified = _stability(spent, whole)
    by_class = {
        label: sum((spent_in for s, spent_in in classified if s.stability == label), ZERO)
        for label in ("stable", "moderate", "volatile")
    }
    judged = sum(by_class.values(), ZERO)

    totals = monthly_totals(spent, whole, spend)
    change = pct_change(totals[-2], totals[-1]) if len(totals) >= 2 else None

    return Behaviour(
        date_from=period.first_day if period else None,
        date_to=period.last_day if period else None,
        by_weekday=weekdays,
        weekday=weekday,
        weekend=weekend,
        weekend_bias_pct=pct_change(unrounded[0], unrounded[1]),
        seasonality=_seasonality(spent, whole),
        stability=tuple(s for s, _ in classified),
        stable_share_pct=share_pct(by_class["stable"], judged),
        moderate_share_pct=share_pct(by_class["moderate"], judged),
        volatile_share_pct=share_pct(by_class["volatile"], judged),
        expense_change_pct=change,
    )
