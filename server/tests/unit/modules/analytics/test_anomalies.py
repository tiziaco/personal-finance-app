"""Anomalies: single expenses far above their trailing window, and categories spiking lately."""

import datetime as dt
import random
from decimal import Decimal

import pytest

from app.modules.analytics.domain.anomalies import CategorySpike, Outlier, find_anomalies
from tests.unit.modules.analytics.rows import row

pytestmark = pytest.mark.unit

BASE = [
    row(f"2026-03-0{d}", a)
    for d, a in zip(range(1, 6), ["-10.00", "-12.00", "-10.00", "-12.00", "-10.00"], strict=True)
]


def test_flags_an_expense_far_above_its_trailing_window():
    rows = BASE + [row("2026-03-06", "-100.00", merchant="Big"), row("2026-03-06", "-11.00", merchant="Small")]
    result = find_anomalies(rows)
    assert result.outliers == (
        Outlier(dt.date(2026, 3, 6), "Big", "shopping", Decimal("100.00"), 91.04, Decimal("10.80")),
    )


def test_fewer_than_five_prior_expenses_never_flag():
    rows = BASE[:4] + [row("2026-03-05", "-1000.00")]
    assert find_anomalies(rows).outliers == ()


def test_the_window_ends_window_days_back():
    rows = [
        row(f"2026-02-0{d}", a)
        for d, a in zip(range(1, 6), ["-10.00", "-12.00", "-10.00", "-12.00", "-10.00"], strict=True)
    ]
    rows.append(row("2026-03-07", "-100.00"))  # 30 days back is 5 Feb: only one prior expense in the window
    assert find_anomalies(rows).outliers == ()
    assert len(find_anomalies(rows, window_days=35).outliers) == 1


def test_identical_prior_expenses_have_no_spread_and_never_flag():
    rows = [row(f"2026-03-0{d}", "-10.00") for d in range(1, 6)] + [row("2026-03-06", "-500.00")]
    assert find_anomalies(rows).outliers == ()


def test_category_spikes_against_the_rest_of_the_range():
    rows = [
        row("2026-01-10", "-150.00", category="food_groceries"),
        row("2026-01-20", "-100.00", category="bars_restaurants"),
        row("2026-02-10", "-150.00", category="food_groceries"),
        row("2026-02-20", "-100.00", category="bars_restaurants"),
        row("2026-03-10", "-400.00", category="food_groceries"),
        row("2026-03-12", "-120.00", category="bars_restaurants"),
        row("2026-03-15", "-500.00", category="travel_holidays"),  # no history: no baseline, no spike
    ]
    result = find_anomalies(rows, date_from=dt.date(2026, 1, 1), date_to=dt.date(2026, 3, 31))
    assert (result.spike_window_start, result.spike_window_end) == (dt.date(2026, 3, 2), dt.date(2026, 3, 31))
    assert result.spikes == (CategorySpike("food_groceries", Decimal("400.00"), Decimal("150.00"), 166.67),)


def test_less_than_thirty_days_of_history_has_no_spikes():
    rows = [row("2026-02-20", "-10.00"), row("2026-03-10", "-400.00")]
    result = find_anomalies(rows, date_from=dt.date(2026, 2, 15), date_to=dt.date(2026, 3, 31))
    assert result.spikes == ()


def test_empty_input():
    result = find_anomalies([])
    assert result.outliers == () and result.spikes == ()
    assert result.spike_window_start is None


def test_an_expense_near_the_earliest_date_does_not_overflow():
    result = find_anomalies([row("0001-01-02", "-10.00"), row("0001-01-03", "-5.00")])
    assert result.outliers == ()
    assert result.spike_window_start == dt.date.min


def _brute_force_outliers(rows, std_threshold, window_days):
    """The straightforward O(n²) reading of the rule, to pin the bisect version against."""
    from statistics import mean, pstdev

    spent = sorted((r for r in rows if r.amount < 0), key=lambda r: r.date)
    found = []
    for current in spent:
        start = current.date - dt.timedelta(days=window_days)
        window = [-r.amount for r in spent if start <= r.date < current.date]
        if len(window) < 5 or pstdev(window) == 0:
            continue
        z = float((-current.amount - mean(window)) / pstdev(window))
        if z > std_threshold:
            found.append((current.date, current.merchant, round(z, 2)))
    return sorted(found, key=lambda t: (-t[2], t[0]))[:20]


@pytest.mark.parametrize("window_days", [7, 30, 90])
def test_outliers_match_a_brute_force_reference_over_two_years(window_days):
    rng = random.Random(42)
    first = dt.date(2024, 1, 1)
    rows = [
        row(
            (first + dt.timedelta(days=rng.randrange(730))).isoformat(),
            f"-{rng.choice([rng.randint(5, 40), rng.randint(200, 900)])}.00",
            merchant=f"m{i}",
        )
        for i in range(5000)
    ]
    expected = _brute_force_outliers(rows, 2.5, window_days)
    got = [(o.date, o.merchant, o.z_score) for o in find_anomalies(rows, 2.5, window_days).outliers]
    assert expected and got == expected
