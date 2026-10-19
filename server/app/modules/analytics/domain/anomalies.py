"""Anomalies: expenses far above their trailing window (their category's, or all one-off spending when it is thin), and categories spending more than usual lately."""

import datetime as dt
from bisect import bisect_left
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal, localcontext
from typing import Literal, Optional

from app.modules.analytics.domain._aggregate import Row, expenses, group_by, money, spend, total_spend
from app.modules.analytics.domain.period import Period

MIN_WINDOW_EXPENSES = 5
MAX_OUTLIERS = 20
SPIKE_DAYS = 30
SPIKE_MIN_PCT = 50.0
SPIKE_MIN_SHARE_OF_MONTH = Decimal("0.05")
FALLBACK_EXCLUDED = frozenset({"atm", "savings_investments"})  # money moved, not spent


@dataclass(frozen=True)
class Outlier:
    """One expense far above the earlier expenses in its trailing window: its category's, or all spending's.

    compared_with is "category" when the category's window held at least MIN_WINDOW_EXPENSES expenses,
    "all" when it held fewer and the expense was compared with all one-off spending instead.
    """

    date: dt.date
    merchant: str
    category: str
    amount: Decimal
    z_score: float
    window_mean: Decimal
    compared_with: Literal["category", "all"]


@dataclass(frozen=True)
class _Score:
    """An expense against its window: z and window_mean are None with fewer than MIN_WINDOW_EXPENSES in it; z alone is None with no spread."""

    row: Row
    n: int
    z: Optional[float]
    window_mean: Optional[Decimal]


@dataclass(frozen=True)
class CategorySpike:
    """A category whose period's last 30 days spend well above its average 30 days before them."""

    category: str
    recent_total: Decimal
    baseline_30d: Decimal
    increase_amount: Decimal
    spike_pct: float


@dataclass(frozen=True)
class Anomalies:
    """The outliers and category spikes over a period."""

    date_from: Optional[dt.date]
    date_to: Optional[dt.date]
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


def _scores(spent: Sequence[Row], period: Period, window_days: int) -> list[_Score]:
    """Each in-period expense against the expenses of the window_days days before its own day.

    spent is the expenses to compare, earlier ones included: a window may reach before the period.
    Prefix sums of the amounts and their squares give each window's mean and spread in O(1),
    exactly: with n expenses summing to s, squares to q, the spread is √(nq − s²) ÷ n and an
    expense x scores (nx − s) ÷ √(nq − s²).
    """
    ordered = sorted(spent, key=lambda r: r.date)
    dates = [r.date for r in ordered]
    scores: list[_Score] = []
    with localcontext() as ctx:
        ctx.prec = 60  # every sum below stays exact for 2-decimal amounts
        sums, squares = [Decimal(0)], [Decimal(0)]
        for r in ordered:
            sums.append(sums[-1] + spend(r))
            squares.append(squares[-1] + spend(r) * spend(r))
        for current in ordered:
            if not period.contains(current.date):
                continue
            low = bisect_left(dates, _days_before(current.date, window_days))
            high = bisect_left(dates, current.date)
            n = high - low
            if n < MIN_WINDOW_EXPENSES:
                scores.append(_Score(current, n, None, None))
                continue
            s, q = sums[high] - sums[low], squares[high] - squares[low]
            spread = n * q - s * s
            z = None if spread <= 0 else float((n * spend(current) - s) / spread.sqrt())
            scores.append(_Score(current, n, z, money(s / n)))
    return scores


def _spike_window(period: Period) -> Optional[tuple[dt.date, dt.date]]:
    """The period's last 30 days; None when fewer than 30 days of the period come before them."""
    recent_start = _days_before(period.last_day, SPIKE_DAYS - 1)
    if (recent_start - period.first_day).days < SPIKE_DAYS:
        return None
    return recent_start, period.last_day


def _spikes(spent: Sequence[Row], period: Period, recent_start: dt.date) -> list[CategorySpike]:
    """Each category's last 30 days against its average 30 days since the period's start.

    Flagged above SPIKE_MIN_PCT, and only when the increase is worth SPIKE_MIN_SHARE_OF_MONTH of the
    period's average monthly spend: a €1 → €40 category is not news.
    """
    baseline_days = (recent_start - period.first_day).days
    floor = SPIKE_MIN_SHARE_OF_MONTH * total_spend(spent) / period.weight()
    spikes: list[CategorySpike] = []
    for category, group in group_by(spent, lambda r: r.category).items():
        recent = total_spend(r for r in group if r.date >= recent_start)
        before = total_spend(r for r in group if r.date < recent_start)
        if before == 0 or recent == 0:
            continue
        baseline = before * SPIKE_DAYS / baseline_days
        pct = round(float((recent / baseline - 1) * 100), 2)
        increase = recent - money(baseline)  # in the response's cents, so recent − baseline adds up
        if pct > SPIKE_MIN_PCT and increase >= floor:
            spikes.append(CategorySpike(category, recent, money(baseline), increase, pct))
    return sorted(spikes, key=lambda s: (-s.increase_amount, s.category))


def find_anomalies(
    rows: Sequence[Row],
    period: Optional[Period],
    std_threshold: float = 2.5,
    window_days: int = 30,
) -> Anomalies:
    """Outliers by trailing z-score, and category spikes in the period's last 30 days.

    An expense is scored against its own category's window; when that holds fewer than MIN_WINDOW_EXPENSES
    expenses, against all one-off spending's window instead, but only if it is not atm or savings_investments
    and is worth SPIKE_MIN_SHARE_OF_MONTH of the period's average monthly spend.

    rows are all the usable rows: outlier windows draw on expenses before the period. Recurring-flagged
    expenses are left out of the outliers, as candidates and from every window.
    """
    if period is None:
        return Anomalies(None, None, std_threshold, window_days, (), (), None, None)
    one_off = [r for r in expenses(rows) if not r.is_recurring]
    overall = {id(score.row): score for score in _scores(one_off, period, window_days)}
    floor = SPIKE_MIN_SHARE_OF_MONTH * total_spend(expenses(period.rows(rows))) / period.weight()
    outliers: list[Outlier] = []
    for category, group in group_by(one_off, lambda r: r.category).items():
        for score in _scores(group, period, window_days):
            compared_with: Literal["category", "all"] = "category"
            if score.n < MIN_WINDOW_EXPENSES:
                if category in FALLBACK_EXCLUDED or spend(score.row) < floor:
                    continue
                score, compared_with = overall[id(score.row)], "all"
            if score.z is not None and score.window_mean is not None and score.z > std_threshold:
                r = score.row
                outliers.append(
                    Outlier(
                        r.date,
                        r.merchant,
                        r.category,
                        money(spend(r)),
                        round(score.z, 2),
                        score.window_mean,
                        compared_with,
                    )
                )
    outliers.sort(key=lambda o: (-o.z_score, o.date, o.category, o.merchant))
    window = _spike_window(period)
    spikes = _spikes(expenses(period.rows(rows)), period, window[0]) if window else []
    return Anomalies(
        date_from=period.first_day,
        date_to=period.last_day,
        std_threshold=std_threshold,
        window_days=window_days,
        outliers=tuple(outliers[:MAX_OUTLIERS]),
        spikes=tuple(spikes),
        spike_window_start=window[0] if window else None,
        spike_window_end=window[1] if window else None,
    )
