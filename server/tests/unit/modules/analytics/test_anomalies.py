"""Anomalies: single expenses far above their category's trailing window, and categories spiking lately."""

import datetime as dt
import random
from decimal import Decimal
from statistics import mean

import pytest

from app.modules.analytics.domain._aggregate import money
from app.modules.analytics.domain.anomalies import CategorySpike, Outlier, find_anomalies
from app.modules.analytics.domain.period import resolve_period
from tests.unit.modules.analytics.rows import row

pytestmark = pytest.mark.unit

TODAY = dt.date(2026, 10, 16)

BASE = [
    row(f"2026-03-0{d}", a)
    for d, a in zip(range(1, 6), ["-10.00", "-12.00", "-10.00", "-12.00", "-10.00"], strict=True)
]


def analyse(rows, std_threshold=2.5, window_days=30, **period):
    return find_anomalies(rows, resolve_period(rows, TODAY, **period), std_threshold, window_days)


def days(first: str, last: str):
    """Every day from first to last, inclusive."""
    day, end = dt.date.fromisoformat(first), dt.date.fromisoformat(last)
    while day <= end:
        yield day
        day += dt.timedelta(days=1)


def test_flags_an_expense_far_above_its_trailing_window():
    rows = BASE + [row("2026-03-06", "-100.00", merchant="Big"), row("2026-03-06", "-11.00", merchant="Small")]
    result = analyse(rows)
    assert result.outliers == (
        Outlier(dt.date(2026, 3, 6), "Big", "shopping", Decimal("100.00"), 91.04, Decimal("10.80")),
    )
    assert (result.date_from, result.date_to) == (dt.date(2026, 3, 1), dt.date(2026, 3, 31))


def test_fewer_than_five_prior_expenses_never_flag():
    rows = BASE[:4] + [row("2026-03-05", "-1000.00")]
    assert analyse(rows).outliers == ()


def test_the_window_ends_window_days_back():
    rows = [
        row(f"2026-02-0{d}", a)
        for d, a in zip(range(1, 6), ["-10.00", "-12.00", "-10.00", "-12.00", "-10.00"], strict=True)
    ]
    rows.append(row("2026-03-07", "-100.00"))  # 30 days back is 5 Feb: only one prior expense in the window
    assert analyse(rows).outliers == ()
    assert len(analyse(rows, window_days=35).outliers) == 1


def test_identical_prior_expenses_have_no_spread_and_never_flag():
    rows = [row(f"2026-03-0{d}", "-10.00") for d in range(1, 6)] + [row("2026-03-06", "-500.00")]
    assert analyse(rows).outliers == ()


@pytest.mark.parametrize("rent_category", ["housing", "food_groceries"])
def test_a_recurring_expense_is_neither_an_outlier_nor_in_a_window(rent_category):
    rows = [
        row(day.isoformat(), f"-{10 + 10 * (i % 4)}.00", category="food_groceries")
        for i, day in enumerate(days("2026-04-01", "2026-09-30"))
    ]
    rows += [
        row(f"2026-{m:02d}-01", "-900.00", merchant="Landlord", category=rent_category, recurring=True)
        for m in range(4, 10)
    ]
    rows.append(row("2026-07-02", "-200.00", merchant="Big shop", category="food_groceries"))  # the day after rent
    result = analyse(rows)
    assert [o.merchant for o in result.outliers] == ["Big shop"]


def test_an_outlier_is_compared_with_its_own_category_from_before_the_period():
    groceries = [row(day.isoformat(), "-10.00", category="food_groceries") for day in days("2026-07-01", "2026-09-30")]
    dining_days = [day for day in days("2026-07-01", "2026-09-30") if day.weekday() in (1, 4)]  # Tuesday, Friday
    dining = [  # €30 on the 1st, up to €50 on the 21st, back to €30 on the 22nd
        row(day.isoformat(), f"-{30 + (day.day - 1) % 21}.00", merchant="Bistro", category="bars_restaurants")
        for day in dining_days
    ]
    early = row("2026-08-05", "-400.00", merchant="Banquet", category="bars_restaurants")  # before the period
    feast = row("2026-09-20", "-400.00", merchant="Feast", category="bars_restaurants")
    result = analyse(groceries + dining + [early, feast], months=1)

    window = [-r.amount for r in dining if dt.date(2026, 8, 21) <= r.date < feast.date]
    assert min(r.date for r in dining if r.date >= dt.date(2026, 8, 21)).month == 8  # the window reaches into August
    flagged = [o for o in result.outliers if o.merchant == "Feast"]
    assert len(flagged) == 1
    assert (flagged[0].date, flagged[0].category, flagged[0].amount) == (
        feast.date,
        "bars_restaurants",
        Decimal("400.00"),
    )
    assert flagged[0].window_mean == money(mean(window))
    assert all(result.date_from <= o.date <= result.date_to for o in result.outliers)


@pytest.mark.parametrize(("recent_gift", "spiking"), [("-40.00", []), ("-100.00", ["gifts"])])
def test_a_spike_too_small_against_monthly_spend_is_not_flagged(recent_gift, spiking):
    rows = [row(day.isoformat(), "-30.00", category="food_groceries") for day in days("2026-01-01", "2026-09-30")]
    rows += [row("2026-01-15", "-10.00", category="gifts"), row("2026-09-20", recent_gift, category="gifts")]
    result = analyse(rows)
    # Gifts rise far beyond 50% either way; €38.77 is under 5% of ~€915 a month, €98.77 is not.
    assert [s.category for s in result.spikes] == spiking
    assert (result.spike_window_start, result.spike_window_end) == (dt.date(2026, 9, 1), dt.date(2026, 9, 30))


def test_spikes_are_ranked_by_the_increase_in_euros():
    rows = []
    for m in ("06", "07", "08"):
        rows += [row(f"2026-{m}-{d:02d}", "-75.00", category="food_groceries") for d in (3, 10, 17, 24)]
        rows.append(row(f"2026-{m}-15", "-10.00", category="bars_restaurants"))
    rows += [row(f"2026-09-{d:02d}", "-100.00", category="food_groceries") for d in (1, 4, 8, 12, 16, 20, 24)]
    rows.append(row("2026-09-15", "-100.00", category="bars_restaurants"))
    result = analyse(rows)
    assert (result.spike_window_start, result.spike_window_end) == (dt.date(2026, 9, 1), dt.date(2026, 9, 30))
    # Baseline 1 Jun–31 Aug, 92 days. Dining rises more in percent, groceries more in euros.
    assert result.spikes == (
        CategorySpike("food_groceries", Decimal("700.00"), Decimal("293.48"), Decimal("406.52"), 138.52),
        CategorySpike("bars_restaurants", Decimal("100.00"), Decimal("9.78"), Decimal("90.22"), 922.22),
    )
    assert all(s.increase_amount > 0 for s in result.spikes)


def test_the_baseline_starts_where_the_data_does():
    rows = [row(day.isoformat(), "-10.00", category="food_groceries") for day in days("2026-06-01", "2026-10-15")]
    result = analyse(rows, date_from=dt.date(2026, 1, 1))
    assert (result.date_from, result.date_to) == (dt.date(2026, 6, 1), dt.date(2026, 10, 15))
    assert (result.spike_window_start, result.spike_window_end) == (dt.date(2026, 9, 16), dt.date(2026, 10, 15))
    assert result.spikes == ()


def test_less_than_thirty_days_of_baseline_is_not_checked():
    rows = [row(day.isoformat(), "-10.00") for day in days("2026-08-22", "2026-09-30")]  # 40 days
    result = analyse(rows)
    assert (result.date_from, result.date_to) == (dt.date(2026, 8, 22), dt.date(2026, 9, 30))
    assert result.spikes == ()
    assert result.spike_window_start is None and result.spike_window_end is None


def test_category_spikes_against_the_rest_of_the_period():
    rows = [
        row("2026-01-05", "-150.00", category="food_groceries"),
        row("2026-01-20", "-100.00", category="bars_restaurants"),
        row("2026-02-10", "-150.00", category="food_groceries"),
        row("2026-02-20", "-100.00", category="bars_restaurants"),
        row("2026-03-10", "-400.00", category="food_groceries"),
        row("2026-03-12", "-120.00", category="bars_restaurants"),
        row("2026-03-15", "-500.00", category="travel_holidays"),  # no history: no baseline, no spike
    ]
    result = analyse(rows, date_from=dt.date(2026, 1, 1), date_to=dt.date(2026, 3, 31))
    assert (result.spike_window_start, result.spike_window_end) == (dt.date(2026, 3, 2), dt.date(2026, 3, 31))
    assert result.spikes == (
        CategorySpike("food_groceries", Decimal("400.00"), Decimal("150.00"), Decimal("250.00"), 166.67),
    )


def test_no_period():
    result = find_anomalies([], None)
    assert result.outliers == () and result.spikes == ()
    assert (result.date_from, result.date_to) == (None, None)
    assert (result.spike_window_start, result.spike_window_end) == (None, None)


def test_an_expense_near_the_earliest_date_does_not_overflow():
    rows = [row("0001-01-02", "-10.00"), row("0001-01-03", "-5.00")]
    result = analyse(rows)
    assert result.outliers == ()
    assert result.spike_window_start is None


def _brute_force_outliers(rows, first_day, std_threshold, window_days):
    """The straightforward O(n²) reading of the rule, to pin the prefix-sum version against."""
    from statistics import pstdev

    spent = sorted((r for r in rows if r.amount < 0 and not r.is_recurring), key=lambda r: r.date)
    found = []
    for current in spent:
        if current.date < first_day:
            continue
        start = current.date - dt.timedelta(days=window_days)
        window = [-r.amount for r in spent if r.category == current.category and start <= r.date < current.date]
        if len(window) < 5 or pstdev(window) == 0:
            continue
        z = float((-current.amount - mean(window)) / pstdev(window))
        if z > std_threshold:
            found.append((current.date, current.merchant, round(z, 2)))
    return sorted(found, key=lambda t: (-t[2], t[0], t[1]))[:20]


@pytest.mark.parametrize("window_days", [7, 30, 90])
def test_outliers_match_a_brute_force_reference_over_two_years(window_days):
    rng = random.Random(42)
    first = dt.date(2024, 1, 1)
    rows = [
        row(
            (first + dt.timedelta(days=rng.randrange(730))).isoformat(),
            f"-{rng.randint(200, 900) if rng.random() < 0.03 else rng.randint(5, 40)}.00",
            merchant=f"m{i:04d}",
            category=rng.choice(["food_groceries", "shopping"]),
            recurring=rng.random() < 0.1,
        )
        for i in range(5000)
    ]
    period = resolve_period(rows, TODAY, months=12)  # 2025: windows in early January reach into 2024
    expected = _brute_force_outliers(rows, period.first_day, 2.5, window_days)
    got = [(o.date, o.merchant, o.z_score) for o in find_anomalies(rows, period, 2.5, window_days).outliers]
    assert expected and got == expected
