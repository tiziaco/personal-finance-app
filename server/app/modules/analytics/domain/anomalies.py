"""Anomalies: expenses far above their trailing window, and categories spending more than usual lately."""

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from statistics import mean, pstdev
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


def _outliers(spent: Sequence[Row], std_threshold: float, window_days: int) -> list[Outlier]:
    """Each expense against the expenses of the window_days days before its own day."""
    ordered = sorted(spent, key=lambda r: r.date)
    found: list[Outlier] = []
    for current in ordered:
        start = current.date - dt.timedelta(days=window_days)
        window = [spend(r) for r in ordered if start <= r.date < current.date]
        if len(window) < MIN_WINDOW_EXPENSES:
            continue
        spread = pstdev(window)
        if spread == 0:
            continue
        centre = mean(window)
        z = float((spend(current) - centre) / spread)
        if z > std_threshold:
            found.append(
                Outlier(
                    current.date, current.merchant, current.category, money(spend(current)), round(z, 2), money(centre)
                )
            )
    found.sort(key=lambda o: (-o.z_score, o.date))
    return found[:MAX_OUTLIERS]


def _spikes(spent: Sequence[Row], start: dt.date, end: dt.date) -> list[CategorySpike]:
    """The last 30 days per category against its average 30 days over the rest of the range."""
    recent_start = end - dt.timedelta(days=SPIKE_DAYS - 1)
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
    covered = span(spent, date_from, date_to)
    spikes = _spikes(spent, *covered) if covered else []
    return Anomalies(
        std_threshold=std_threshold,
        window_days=window_days,
        outliers=tuple(_outliers(spent, std_threshold, window_days)),
        spikes=tuple(spikes),
        spike_window_start=covered[1] - dt.timedelta(days=SPIKE_DAYS - 1) if covered else None,
        spike_window_end=covered[1] if covered else None,
    )
