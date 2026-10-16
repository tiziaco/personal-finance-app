"""Categories: where the money goes, how often, and which categories grow."""

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Optional

from app.modules.analytics.domain._aggregate import (
    ZERO,
    Row,
    average,
    expenses,
    group_by,
    money,
    pct_change,
    share_pct,
    spend,
    total_spend,
)
from app.modules.analytics.domain.period import Period, previous_period

TREND_SIZE = 5


@dataclass(frozen=True)
class CategorySpend:
    """One category's expense total, count, average and share of all expenses, and the previous period's total."""

    category: str
    total: Decimal
    count: int
    average: Decimal
    share_pct: float
    previous_total: Optional[Decimal] = None
    change_pct: Optional[float] = None


@dataclass(frozen=True)
class CategoryTrend:
    """One category's monthly average over the earlier and the later half of the period's whole months."""

    category: str
    earlier_monthly_average: Decimal
    later_monthly_average: Decimal
    change_amount: Decimal
    change_pct: Optional[float]


@dataclass(frozen=True)
class CategoryBreakdown:
    """Category rankings by spend and by frequency, and the categories growing and declining the most."""

    date_from: Optional[dt.date]
    date_to: Optional[dt.date]
    previous_date_from: Optional[dt.date]
    previous_date_to: Optional[dt.date]
    total_expenses: Decimal
    top_categories: tuple[CategorySpend, ...]
    by_frequency: tuple[CategorySpend, ...]
    top_growing: tuple[CategoryTrend, ...]
    top_declining: tuple[CategoryTrend, ...]


def category_spend(rows: Sequence[Row]) -> list[CategorySpend]:
    """Expenses per category, ranked by total (ties by slug); no previous period."""
    spent = expenses(rows)
    whole = total_spend(spent)
    items = []
    for category, group in group_by(spent, lambda r: r.category).items():
        total = total_spend(group)
        items.append(CategorySpend(category, total, len(group), average(total, len(group)), share_pct(total, whole)))
    return sorted(items, key=lambda i: (-i.total, i.category))


def _against(items: Sequence[CategorySpend], before: Optional[Sequence[Row]]) -> list[CategorySpend]:
    """The items with the previous period's total and the change from it; unchanged without a previous period."""
    if before is None:
        return list(items)
    totals = {c: total_spend(g) for c, g in group_by(expenses(before), lambda r: r.category).items()}
    return [
        replace(i, previous_total=(prev := totals.get(i.category, ZERO)), change_pct=pct_change(prev, i.total))
        for i in items
    ]


def _trends(rows: Sequence[Row], period: Period) -> list[CategoryTrend]:
    """Each category's monthly average in the earlier and later half of the whole months; the middle month is left out."""
    whole = period.whole_months()
    half = len(whole) // 2
    if half == 0:
        return []
    earlier, later = whole[:half], whole[-half:]

    def spent(months: Sequence, category_rows: Sequence[Row]) -> Decimal:
        starts = {m.start.replace(day=1) for m in months}
        return sum((spend(r) for r in category_rows if r.date.replace(day=1) in starts), ZERO)

    trends = []
    for category, group in group_by(expenses(period.rows(rows)), lambda r: r.category).items():
        before, after = spent(earlier, group) / half, spent(later, group) / half
        if before == after == 0:
            continue
        trends.append(
            CategoryTrend(category, money(before), money(after), money(after - before), pct_change(before, after))
        )
    return trends


def category_breakdown(
    rows: Sequence[Row], period: Optional[Period], top_n: int = 10, *, today: dt.date
) -> CategoryBreakdown:
    """Ranked category spend against the previous period, and the categories growing and declining the most."""
    if period is None:
        return CategoryBreakdown(None, None, None, None, ZERO, (), (), (), ())
    before = previous_period(period, rows, today)
    covered = period.rows(rows)
    ranked = _against(category_spend(covered), before.rows(rows) if before else None)
    trends = _trends(rows, period)
    growing = sorted((t for t in trends if t.change_amount > 0), key=lambda t: (-t.change_amount, t.category))
    declining = sorted((t for t in trends if t.change_amount < 0), key=lambda t: (t.change_amount, t.category))
    return CategoryBreakdown(
        date_from=period.first_day,
        date_to=period.last_day,
        previous_date_from=before.first_day if before else None,
        previous_date_to=before.last_day if before else None,
        total_expenses=total_spend(expenses(covered)),
        top_categories=tuple(ranked[:top_n]),
        by_frequency=tuple(sorted(ranked, key=lambda i: (-i.count, -i.total, i.category))[:top_n]),
        top_growing=tuple(growing[:TREND_SIZE]),
        top_declining=tuple(declining[:TREND_SIZE]),
    )
