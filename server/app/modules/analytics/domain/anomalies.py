"""Anomalies: expenses far above their trailing window, and categories spending more than usual lately."""

import datetime as dt
from bisect import bisect_left
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal, localcontext
from typing import Optional

from app.modules.analytics.domain._aggregate import Row, expenses, group_by, money, span, spend, total_spend

MIN_WINDOW_EXPENSES = 5
MAX_OUTLIERS = 20
SPIKE_DAYS = 30
SPIKE_MIN_PCT = 50.0


@dataclass(frozen=True)
class Outlier:
    """One expense far above the expenses of its trailing window."""

    date: dt.date
    merchant: str
    category: str
    amount: Decimal
    z_score: float
    window_mean: Decimal


@dataclass(frozen=True)
class CategorySpike:
    """A category whose last 30 days spend well above its average 30 days."""

    category: str
    recent_total: Decimal
    baseline_30d: Decimal
    spike_pct: float


@dataclass(frozen=True)
class Anomalies:
    """The outliers and category spikes over a range."""

    std_threshold: float
    window_days: int
    outliers: tuple[Outlier, ...]
    spikes: tuple[CategorySpike, ...]
    spike_window_start: Optional[dt.date]
    spike_window_end: Optional[dt.date]


def _days_before(day: dt.date, days: int) -> dt.date:
    """The day `days` days earlier, stopping at the earliest date the calendar holds."""
    try:
        return day - dt.timedelta(days=days)
    except OverflowError:
        return dt.date.min


def _outliers(spent: Sequence[Row], std_threshold: float, window_days: int) -> list[Outlier]:
    """Each expense against the expenses of the window_days days before its own day.

    Prefix sums of the amounts and their squares give each window's mean and spread in O(1),
    exactly: with n expenses summing to s, squares to q, the spread is √(nq − s²) ÷ n and an
    expense x scores (nx − s) ÷ √(nq − s²).
    """
    ordered = sorted(spent, key=lambda r: r.date)
    dates = [r.date for r in ordered]
    found: list[Outlier] = []
    with localcontext() as ctx:
        ctx.prec = 60  # every sum below stays exact for 2-decimal amounts
        sums, squares = [Decimal(0)], [Decimal(0)]
        for r in ordered:
            sums.append(sums[-1] + spend(r))
            squares.append(squares[-1] + spend(r) * spend(r))
        for current in ordered:
            low = bisect_left(dates, _days_before(current.date, window_days))
            high = bisect_left(dates, current.date)
            n = high - low
            if n < MIN_WINDOW_EXPENSES:
                continue
            s, q = sums[high] - sums[low], squares[high] - squares[low]
            spread = n * q - s * s
            if spread <= 0:
                continue
            z = float((n * spend(current) - s) / spread.sqrt())
            if z > std_threshold:
                found.append(
                    Outlier(
                        current.date,
                        current.merchant,
                        current.category,
                        money(spend(current)),
                        round(z, 2),
                        money(s / n),
                    )
                )
    found.sort(key=lambda o: (-o.z_score, o.date))
    return found[:MAX_OUTLIERS]


def _spikes(spent: Sequence[Row], start: dt.date, end: dt.date) -> list[CategorySpike]:
    """The last 30 days per category against its average 30 days over the rest of the range."""
    recent_start = _days_before(end, SPIKE_DAYS - 1)
    baseline_days = (recent_start - start).days
    if baseline_days < SPIKE_DAYS:
        return []
    spikes: list[CategorySpike] = []
    for category, group in group_by(spent, lambda r: r.category).items():
        recent = total_spend(r for r in group if recent_start <= r.date <= end)
        before = total_spend(r for r in group if r.date < recent_start)
        if before == 0 or recent == 0:
            continue
        baseline = before * SPIKE_DAYS / baseline_days
        pct = round(float((recent / baseline - 1) * 100), 2)
        if pct > SPIKE_MIN_PCT:
            spikes.append(CategorySpike(category, recent, money(baseline), pct))
    return sorted(spikes, key=lambda s: (-s.spike_pct, s.category))


def find_anomalies(
    rows: Sequence[Row],
    std_threshold: float = 2.5,
    window_days: int = 30,
    date_from: Optional[dt.date] = None,
    date_to: Optional[dt.date] = None,
) -> Anomalies:
    """Outliers by trailing z-score, and category spikes in the range's last 30 days."""
    spent = expenses(rows)
    covered = span(rows, date_from, date_to)
    spikes = _spikes(spent, *covered) if covered else []
    return Anomalies(
        std_threshold=std_threshold,
        window_days=window_days,
        outliers=tuple(_outliers(spent, std_threshold, window_days)),
        spikes=tuple(spikes),
        spike_window_start=_days_before(covered[1], SPIKE_DAYS - 1) if covered else None,
        spike_window_end=covered[1] if covered else None,
    )
