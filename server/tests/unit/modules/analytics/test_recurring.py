"""Recurring: what the stored flag marks, its billing rhythm and monthly cost, and unflagged look-alikes."""

import datetime as dt
from decimal import Decimal

import pytest

from app.modules.analytics.domain.period import resolve_period
from app.modules.analytics.domain.recurring import (
    HiddenSubscription,
    RecurringMerchant,
    recurring_analysis,
)
from tests.unit.modules.analytics.rows import row

pytestmark = pytest.mark.unit

TODAY = dt.date(2026, 10, 16)


def analyse(rows, **period):
    """The analysis over the period the arguments resolve to; months=12 unless given."""
    period = period or {"months": 12}
    return recurring_analysis(rows, resolve_period(rows, TODAY, **period))


def monthly(day: int, first: str, last: str, amount: str, merchant: str, recurring: bool = True):
    """One charge on `day` of every month from `first` to `last` (YYYY-MM, inclusive)."""
    year, month = map(int, first.split("-"))
    rows = []
    while f"{year:04d}-{month:02d}" <= last:
        rows.append(row(f"{year:04d}-{month:02d}-{day:02d}", amount, merchant=merchant, recurring=recurring))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return rows


NETFLIX = monthly(5, "2026-01", "2026-09", "-10.00", "Netflix")

ROWS = [
    row("2026-01-01", "-10.00", merchant="Netflix", recurring=True),
    row("2026-01-02", "-3.00", merchant="Coffee"),
    row("2026-01-15", "-900.00", merchant="Landlord", recurring=True),
    row("2026-01-20", "-100.00", merchant="IKEA"),
    row("2026-01-27", "2000.00", merchant="Employer", recurring=True),  # income: ignored
    row("2026-02-01", "-10.00", merchant="Netflix", recurring=True),
    row("2026-02-02", "-3.50", merchant="Coffee"),
    row("2026-02-15", "-900.00", merchant="Landlord", recurring=True),
    row("2026-03-01", "-12.00", merchant="Netflix", recurring=True),
]


def test_flagged_spend_and_its_share():
    result = analyse(ROWS)
    assert (result.date_from, result.date_to) == (dt.date(2026, 1, 1), dt.date(2026, 3, 31))
    assert result.total_expenses == Decimal("1938.50")
    assert result.recurring_total == Decimal("1832.00")
    assert result.recurring_count == 5
    assert result.amount_share_pct == 94.51
    assert result.count_share_pct == 62.5  # 5 of 8 expenses


def test_a_monthly_charge_costs_its_median_charge():
    netflix = analyse(NETFLIX).merchants[0]
    assert netflix == RecurringMerchant(
        "Netflix", 9, 9, Decimal("10.00"), 31, Decimal("10.00"), dt.date(2026, 9, 5), True
    )
    assert 28 <= netflix.interval_days <= 31


def test_the_median_charge_is_the_median_not_the_mean():
    rows = [
        row(day, amount, merchant="Netflix", recurring=True)
        for day, amount in (("2026-01-05", "-10.00"), ("2026-02-05", "-10.00"), ("2026-03-05", "-12.00"))
    ]
    assert analyse(rows).merchants[0].median_charge == Decimal("10.00")  # the mean is 10.67


def test_a_single_yearly_charge_is_spread_over_the_period():
    rows = monthly(5, "2025-10", "2026-09", "-10.00", "Netflix") + [
        row("2026-02-14", "-600.00", merchant="Insurance", recurring=True)
    ]
    result = analyse(rows)
    assert (result.date_from, result.date_to) == (dt.date(2025, 10, 1), dt.date(2026, 9, 30))
    insurance = result.merchants[0]
    assert insurance == RecurringMerchant(
        "Insurance", 1, 1, Decimal("600.00"), None, Decimal("50.00"), dt.date(2026, 2, 14), True
    )


def test_a_charge_every_year_costs_a_twelfth_a_month():
    rows = [
        row("2025-02-14", "-600.00", merchant="Insurance", recurring=True),
        row("2026-02-14", "-600.00", merchant="Insurance", recurring=True),
    ]
    insurance = analyse(rows, date_from=dt.date(2025, 1, 1)).merchants[0]
    assert (insurance.interval_days, insurance.monthly_cost) == (365, Decimal("50.00"))


def test_a_quarterly_charge_costs_a_third_a_month():
    rows = [row(day, "-90.00", merchant="Water", recurring=True) for day in ("2026-01-10", "2026-04-10", "2026-07-10")]
    water = analyse(rows).merchants[0]
    assert (water.interval_days, water.monthly_cost) == (91, Decimal("30.00"))


def test_a_charge_more_often_than_monthly_scales_up():
    rows = [row(f"2026-09-{d:02d}", "-7.00", merchant="Cleaner", recurring=True) for d in (1, 15, 29)]
    cleaner = analyse(rows).merchants[0]
    assert cleaner.interval_days == 14
    assert cleaner.monthly_cost == Decimal("15.22")  # 7 × 30.436875 ÷ 14


def test_a_cancelled_merchant_is_inactive_and_leaves_the_monthly_cost():
    gym = monthly(5, "2026-01", "2026-03", "-40.00", "Gym")
    result = analyse(NETFLIX + gym)
    by_name = {m.merchant: m for m in result.merchants}
    assert by_name["Gym"].interval_days == 30  # gaps 31 and 28: the median 29.5 rounds half-up
    assert by_name["Gym"].active is False  # 30 Sep is 209 days after 5 Mar, past 1.5 × 30
    assert by_name["Gym"].last_charge == dt.date(2026, 3, 5)
    assert by_name["Netflix"].active is True
    assert result.monthly_recurring_cost == Decimal("10.00")


def test_active_is_measured_from_the_periods_last_day():
    gym = monthly(5, "2026-01", "2026-03", "-40.00", "Gym")
    result = analyse(NETFLIX + gym, date_from=dt.date(2026, 1, 1), date_to=dt.date(2026, 4, 19))
    gym_result = next(m for m in result.merchants if m.merchant == "Gym")
    assert gym_result.active is True  # 19 Apr is 45 days after 5 Mar: not more than 1.5 × 30


def test_a_first_charge_this_month_costs_itself():
    rows = [row("2026-10-02", "-10.00", merchant="Netflix", recurring=True), row("2026-10-02", "-50.00")]
    result = analyse(rows, months=None)  # the fallback: 1-2 October
    netflix = result.merchants[0]
    assert (netflix.interval_days, netflix.monthly_cost) == (None, Decimal("10.00"))  # not 10 ÷ 2/31
    assert result.monthly_recurring_cost == Decimal("10.00")


@pytest.mark.parametrize("months", [1, 3, 6])
def test_a_yearly_charge_reads_its_rhythm_from_before_the_period(months):
    rows = NETFLIX + [
        row("2025-09-05", "-600.00", merchant="Insurance", recurring=True),
        row("2026-09-05", "-600.00", merchant="Insurance", recurring=True),
    ]
    insurance = next(m for m in analyse(rows, months=months).merchants if m.merchant == "Insurance")
    assert (insurance.charges, insurance.months_charged) == (1, 1)  # scoped to the period
    assert (insurance.interval_days, insurance.monthly_cost, insurance.active) == (365, Decimal("50.00"), True)


def test_charges_on_one_day_are_one_billing_event():
    rows = monthly(5, "2026-01", "2026-09", "-10.00", "Club") + monthly(5, "2026-01", "2026-09", "-10.00", "Club")
    club = analyse(rows).merchants[0]
    assert (club.charges, club.months_charged, club.median_charge) == (18, 9, Decimal("10.00"))
    assert club.interval_days == 31  # between billing days, not the 0 between the two charges of one day
    assert club.monthly_cost == Decimal("20.00")


def test_rows_outside_the_period_are_ignored():
    rows = monthly(5, "2026-01", "2026-09", "-40.00", "Gym")
    gym = analyse(rows, months=3).merchants[0]
    assert (gym.charges, gym.months_charged) == (3, 3)


def test_hidden_subscriptions_look_like_subscriptions():
    rows = (
        NETFLIX
        + monthly(3, "2026-06", "2026-09", "-9.99", "Spotify", recurring=False)
        + [row(f"2026-08-{d:02d}", "-3.50", merchant="Coffee") for d in (4, 11, 18)]  # one month only
        + [row(day.isoformat(), "-35.00", merchant="Grocer") for day in _weekly(dt.date(2026, 6, 1), 17)]  # gap 7
        + [
            row(day, amount, merchant="Varies")  # amounts more than 10% from the median
            for day, amount in (("2026-06-10", "-20.00"), ("2026-07-10", "-45.00"), ("2026-08-10", "-30.00"))
        ]
        + monthly(12, "2026-06", "2026-09", "-79.00", "Pricey", recurring=False)  # over €50
    )
    assert analyse(rows).hidden_subscriptions == (HiddenSubscription("Spotify", 4, 4, Decimal("9.99"), 1.0),)


def test_a_merchant_flagged_once_is_never_a_hidden_subscription():
    rows = monthly(5, "2026-01", "2026-03", "-10.00", "Netflix") + monthly(
        5, "2026-04", "2026-09", "-10.00", "Netflix", recurring=False
    )
    result = analyse(rows)
    assert [m.merchant for m in result.merchants] == ["Netflix"]
    assert result.hidden_subscriptions == ()
    later = analyse(rows, months=3)  # the flagged rows fall before the period
    assert later.merchants == () and later.hidden_subscriptions == ()


def test_hidden_subscriptions_rank_by_monthly_spend():
    rows = (
        monthly(3, "2026-06", "2026-09", "-9.99", "Spotify", recurring=False)
        + monthly(8, "2026-06", "2026-09", "-12.99", "Disney", recurring=False)
        + monthly(9, "2026-06", "2026-09", "-12.99", "apple", recurring=False)
    )
    assert [h.merchant for h in analyse(rows).hidden_subscriptions] == ["apple", "Disney", "Spotify"]


def test_no_period_is_an_empty_analysis():
    result = recurring_analysis([], None)
    assert (result.date_from, result.date_to) == (None, None)
    assert result.recurring_total == Decimal("0.00")
    assert result.amount_share_pct == 0.0
    assert result.merchants == () and result.hidden_subscriptions == ()


def test_a_recurring_merchant_is_its_merchant_key():
    rows = [
        row("2026-01-01", "-10.00", merchant="PAYPAL *NETFLIX 4029357733", recurring=True),
        row("2026-02-01", "-10.00", merchant="NETFLIX.COM", recurring=True),
        row("2026-03-01", "-10.00", merchant="Netflix", recurring=True),
    ]
    assert [(m.merchant, m.charges) for m in analyse(rows).merchants] == [("Netflix", 3)]


def _weekly(start: dt.date, count: int) -> list[dt.date]:
    return [start + dt.timedelta(weeks=i) for i in range(count)]


def test_a_merchant_the_user_unticked_is_never_a_hidden_subscription():
    spotify = monthly(3, "2026-06", "2026-09", "-9.99", "Spotify", recurring=False)
    assert [h.merchant for h in analyse(spotify).hidden_subscriptions] == ["Spotify"]
    unticked = [row("2026-06-03", "-9.99", merchant="Spotify", by_user=True)] + spotify[1:]
    assert analyse(unticked).hidden_subscriptions == ()


def test_an_untick_before_the_period_still_excludes_the_merchant():
    spotify = monthly(3, "2026-07", "2026-09", "-9.99", "Spotify", recurring=False)
    unticked = row("2026-01-03", "-9.99", merchant="Spotify", by_user=True)
    assert [h.merchant for h in analyse(spotify, months=3).hidden_subscriptions] == ["Spotify"]
    assert analyse([unticked, *spotify], months=3).hidden_subscriptions == ()
