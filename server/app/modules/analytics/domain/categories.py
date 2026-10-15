"""Categories: where the money goes, how often, and which categories grow."""

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from app.modules.analytics.domain._aggregate import (
    Row,
    average,
    cv,
    expenses,
    group_by,
    month_range,
    monthly_totals,
    pct_change,
    share_pct,
    span,
    spend,
    total_spend,
)

TREND_SIZE = 5


@dataclass(frozen=True)
class CategorySpend:
    """One category's expense total, count, average and share of all expenses."""

    category: str
    total: Decimal
    count: int
    average: Decimal
    share_pct: float


@dataclass(frozen=True)
class CategoryTrend:
    """One category's spend in its first and last month with spend, its growth and variability."""

    category: str
    first_month_total: Decimal
    last_month_total: Decimal
    growth_pct: float
    cv: Optional[float]


@dataclass(frozen=True)
class CategoryBreakdown:
    """Category rankings by spend and by frequency, and the fastest growing and declining categories."""

    total_expenses: Decimal
    top_categories: tuple[CategorySpend, ...]
    by_frequency: tuple[CategorySpend, ...]
    top_growing: tuple[CategoryTrend, ...]
    top_declining: tuple[CategoryTrend, ...]


def category_spend(rows: Sequence[Row]) -> list[CategorySpend]:
    """Expenses per category, ranked by total (ties by slug)."""
    spent = expenses(rows)
    whole = total_spend(spent)
    items = []
    for category, group in group_by(spent, lambda r: r.category).items():
        total = total_spend(group)
        items.append(CategorySpend(category, total, len(group), average(total, len(group)), share_pct(total, whole)))
    return sorted(items, key=lambda i: (-i.total, i.category))


def _trends(rows: Sequence[Row], months: Sequence[dt.date]) -> list[CategoryTrend]:
    """Growth from each category's first to last month with spend; needs two such months."""
    trends: list[CategoryTrend] = []
    for category, group in group_by(expenses(rows), lambda r: r.category).items():
        series = monthly_totals(group, months, spend)
        with_spend = [total for total in series if total > 0]
        if len(with_spend) < 2:
            continue
        growth = pct_change(with_spend[0], with_spend[-1])
        if growth is None:
            continue
        trends.append(CategoryTrend(category, with_spend[0], with_spend[-1], growth, cv(series)))
    return trends


def category_breakdown(
    rows: Sequence[Row], top_n: int = 10, date_from: Optional[dt.date] = None, date_to: Optional[dt.date] = None
) -> CategoryBreakdown:
    """Ranked category spend, the same ranked by count, and the fastest growing and declining categories."""
    ranked = category_spend(rows)
    covered = span(rows, date_from, date_to)
    trends = _trends(rows, month_range(*covered)) if covered else []
    growing = sorted((t for t in trends if t.growth_pct > 0), key=lambda t: (-t.growth_pct, t.category))
    declining = sorted((t for t in trends if t.growth_pct < 0), key=lambda t: (t.growth_pct, t.category))
    return CategoryBreakdown(
        total_expenses=total_spend(expenses(rows)),
        top_categories=tuple(ranked[:top_n]),
        by_frequency=tuple(sorted(ranked, key=lambda i: (-i.count, -i.total, i.category))[:top_n]),
        top_growing=tuple(growing[:TREND_SIZE]),
        top_declining=tuple(declining[:TREND_SIZE]),
    )
