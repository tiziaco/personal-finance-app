"""The recurring rule (spec §4.3)."""

import csv
import datetime as dt
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

import pytest
from uuid_utils.compat import uuid7

from app.modules.transaction.domain import DETECTED, USER, RecurringRow, detect_recurring, normalise_merchant

pytestmark = pytest.mark.unit

START = dt.date(2025, 1, 5)


def series(gaps: list[int], amount: str = "-9.99", source: str = DETECTED) -> list[RecurringRow]:
    """Rows starting on START, each `gap` days after the previous one."""
    dates = [START]
    for gap in gaps:
        dates.append(dates[-1] + dt.timedelta(days=gap))
    return [RecurringRow(uuid7(), d, Decimal(amount), source) for d in dates]


def verdicts(rows: list[RecurringRow]) -> list[bool]:
    """The verdict of every detected row; a detected row with no verdict raises KeyError."""
    result = detect_recurring(rows)
    return [result[r.id] for r in rows if r.source == DETECTED]


@pytest.mark.parametrize(
    ("gaps", "expected"),
    [
        ([7, 7, 7], True),  # weekly
        ([6, 6, 6], True),  # weekly, lower edge
        ([8, 8, 8], True),  # weekly, upper edge
        ([5, 5, 5], False),  # just under weekly
        ([9, 9, 9], False),  # just over weekly
        ([12, 12, 12], True),  # weekly, one skipped period, lower edge
        ([16, 16, 16], True),  # weekly, one skipped period, upper edge
        ([11, 11, 11], False),  # just under weekly, one skipped period
        ([17, 17, 17], False),  # just over weekly, one skipped period
        ([30, 31], True),  # monthly
        ([26, 35], True),  # monthly, both edges
        ([25, 25], False),  # under monthly, over weekly
        ([36, 36], False),  # over monthly
        ([52, 52], True),  # monthly, one skipped period, lower edge
        ([70, 70], True),  # monthly, one skipped period, upper edge
        ([51, 51], False),  # just under monthly, one skipped period
        ([71, 71], False),  # just over monthly, one skipped period
        ([84, 84], True),  # quarterly, lower edge
        ([98, 98], True),  # quarterly, upper edge
        ([83, 83], False),  # just under quarterly
        ([99, 99], False),  # just over quarterly
        ([91, 91], True),  # quarterly
        ([350, 350], True),  # yearly, lower edge
        ([380, 380], True),  # yearly, upper edge
        ([349, 349], False),  # just under yearly
        ([381, 381], False),  # just over yearly
        ([365, 366], True),  # yearly, three rows
        ([365, 730], True),  # yearly, three rows, one skipped period
        ([365], True),  # yearly, two rows at one amount
        ([730], False),  # yearly, two rows may not skip a period
        ([30], False),  # two rows are never a series
    ],
)
def test_cadences(gaps, expected):
    assert set(verdicts(series(gaps))) == {expected}


LIDL_AMOUNTS = [
    "38.20",
    "41.50",
    "39.90",
    "44.10",
    "40.30",
    "38.80",
    "45.60",
    "42.00",
    "39.10",
    "43.70",
    "40.80",
    "46.00",
]
LIDL_GAPS = [7, 6, 8, 5, 9, 7, 6, 8, 7, 6, 8]


def test_frequent_shopping_with_varying_baskets_is_not_recurring():
    dates = [START]
    for gap in LIDL_GAPS:
        dates.append(dates[-1] + dt.timedelta(days=gap))
    rows = [RecurringRow(uuid7(), d, -Decimal(a), DETECTED) for d, a in zip(dates, LIDL_AMOUNTS, strict=True)]
    assert set(detect_recurring(rows).values()) == {False}


def test_a_fixed_weekly_charge_needs_four_rows():
    assert set(verdicts(series([7, 7, 7]))) == {True}
    assert set(verdicts(series([7, 7]))) == {False}


def test_a_fixed_weekly_charge_may_skip_a_week():
    assert set(verdicts(series([7, 14, 7]))) == {True}


def test_a_weekly_charge_must_hold_its_amount():
    def weekly(amounts: list[str]) -> list[RecurringRow]:
        return [
            RecurringRow(uuid7(), START + dt.timedelta(days=7 * i), Decimal(a), DETECTED)
            for i, a in enumerate(amounts)
        ]

    assert set(verdicts(weekly(["-10.00", "-10.15", "-10.00", "-10.10"]))) == {True}
    assert set(verdicts(weekly(["-10.00", "-10.80", "-10.00", "-10.40"]))) == {False}


def test_an_odd_purchase_in_a_weekly_charges_cluster_is_left_out():
    weekly = series([7, 7, 7], amount="-9.99")
    odd = RecurringRow(uuid7(), START + dt.timedelta(days=10), Decimal("-10.50"), DETECTED)
    result = detect_recurring([*weekly, odd])
    assert [result[r.id] for r in weekly] == [True] * 4
    assert result[odd.id] is False


def test_a_weekly_charge_that_changes_price_is_recurring_at_both_amounts():
    before = series([7] * 19, amount="-3.00")
    after = [
        RecurringRow(uuid7(), before[-1].date + dt.timedelta(days=7 * i), Decimal("-3.20"), DETECTED)
        for i in range(1, 21)
    ]
    assert set(verdicts([*before, *after])) == {True}


def test_a_one_off_purchase_does_not_break_a_weekly_run():
    weekly = series([7] * 29, amount="-60.00")
    odd = RecurringRow(uuid7(), START + dt.timedelta(days=52), Decimal("-65.00"), DETECTED)
    result = detect_recurring([*weekly, odd])
    assert [result[r.id] for r in weekly] == [True] * 30
    assert result[odd.id] is False


def test_two_yearly_charges_at_one_amount_are_recurring():
    assert set(verdicts(series([365], amount="-89.90"))) == {True}


def test_two_yearly_charges_that_differ_are_not_recurring():
    rows = [
        RecurringRow(uuid7(), START, Decimal("-89.90"), DETECTED),
        RecurringRow(uuid7(), START + dt.timedelta(days=365), Decimal("-98.90"), DETECTED),
    ]
    assert set(detect_recurring(rows).values()) == {False}


@pytest.mark.parametrize(
    ("between", "expected"),
    [
        (["-23.10", "-15.80"], False),  # other purchases at the venue
        (["-7.80"], False),  # within ±15 % of the charge, so in its cluster, but another run
        (["5.00"], True),  # money in is judged apart
    ],
)
def test_two_yearly_charges_are_recurring_only_with_nothing_between(between, expected):
    charges = [
        RecurringRow(uuid7(), START, Decimal("-7.42"), DETECTED),
        RecurringRow(uuid7(), START + dt.timedelta(days=372), Decimal("-7.42"), DETECTED),
    ]
    others = [
        RecurringRow(uuid7(), START + dt.timedelta(days=100 * (i + 1)), Decimal(amount), DETECTED)
        for i, amount in enumerate(between)
    ]
    result = detect_recurring([*charges, *others])
    assert [result[r.id] for r in charges] == [expected, expected]


def test_three_yearly_charges_within_fifteen_percent_are_recurring():
    """The ±15 % form: no two rows share an amount, and a purchase between rules out the fixed form."""
    charges = [
        RecurringRow(uuid7(), START, Decimal("-89.90"), DETECTED),
        RecurringRow(uuid7(), START + dt.timedelta(days=365), Decimal("-95.90"), DETECTED),
        RecurringRow(uuid7(), START + dt.timedelta(days=731), Decimal("-98.90"), DETECTED),
    ]
    purchase = RecurringRow(uuid7(), START + dt.timedelta(days=200), Decimal("-12.00"), DETECTED)
    result = detect_recurring([*charges, purchase])
    assert [result[r.id] for r in charges] == [True, True, True]
    assert result[purchase.id] is False


def test_small_yearly_amounts_get_ten_cents_of_slack_not_fifty():
    def pair(second: str) -> list[RecurringRow]:
        return [
            RecurringRow(uuid7(), START, Decimal("-5.68"), DETECTED),
            RecurringRow(uuid7(), START + dt.timedelta(days=365), Decimal(second), DETECTED),
        ]

    assert set(detect_recurring(pair("-5.94")).values()) == {False}
    assert set(detect_recurring(pair("-5.76")).values()) == {True}


def test_one_skipped_period_still_fits():
    assert set(verdicts(series([30, 61, 30, 30]))) == {True}


def test_seeds_do_not_drift():
    """A cluster is anchored on its seed, not on a median that moves as rows join.

    Ten, ten, eleven-forty and eleven-forty all join the 10.00 seed (the tie on count
    goes to the smallest amount), leaving the median at 10.70. 12.00 is 2.00 from the
    seed, outside the band, so it stands alone and is not a series. A running median
    takes it in (1.30 from 10.70, inside the band), making five monthly rows a series.
    The 10.00 and 11.40 rows are True under both, so only the 12.00 verdict separates
    them; this fails under a running median in the rule's own order and in ascending order.
    """
    rows = [
        RecurringRow(uuid7(), START, Decimal("-10.00"), DETECTED),
        RecurringRow(uuid7(), START + dt.timedelta(days=30), Decimal("-11.40"), DETECTED),
        RecurringRow(uuid7(), START + dt.timedelta(days=60), Decimal("-10.00"), DETECTED),
        RecurringRow(uuid7(), START + dt.timedelta(days=90), Decimal("-11.40"), DETECTED),
        RecurringRow(uuid7(), START + dt.timedelta(days=120), Decimal("-12.00"), DETECTED),
    ]
    result = detect_recurring(rows)
    assert [result[r.id] for r in rows[:4]] == [True, True, True, True]
    assert result[rows[4].id] is False


def test_three_quarters_of_the_gaps_must_fit():
    assert set(verdicts(series([30, 30, 30, 10]))) == {True}
    assert set(verdicts(series([30, 30, 10, 10]))) == {False}


def test_an_amount_outside_the_band_is_judged_apart():
    subscription = series([31, 28, 31], amount="-10.00")
    one_off = RecurringRow(uuid7(), START + dt.timedelta(days=40), Decimal("-12.00"), DETECTED)
    result = detect_recurring([*subscription, one_off])
    assert [result[r.id] for r in subscription] == [True] * 4
    assert result[one_off.id] is False


def test_small_amounts_get_a_euro_of_slack():
    rows = [
        RecurringRow(uuid7(), START, Decimal("-2.00"), DETECTED),
        RecurringRow(uuid7(), START + dt.timedelta(days=30), Decimal("-2.80"), DETECTED),
        RecurringRow(uuid7(), START + dt.timedelta(days=60), Decimal("-2.00"), DETECTED),
    ]
    assert set(detect_recurring(rows).values()) == {True}


def test_user_rows_count_as_evidence_and_are_never_judged():
    pinned = series([30], source=USER)
    last = RecurringRow(uuid7(), pinned[-1].date + dt.timedelta(days=30), Decimal("-9.99"), DETECTED)
    result = detect_recurring([*pinned, last])
    assert result == {last.id: True}


def test_money_in_and_money_out_are_judged_apart():
    salary = series([30, 31], amount="2400.00")
    refund = RecurringRow(uuid7(), START + dt.timedelta(days=15), Decimal("-2400.00"), DETECTED)
    result = detect_recurring([*salary, refund])
    assert [result[r.id] for r in salary] == [True, True, True]
    assert result[refund.id] is False


def test_legacy_fixture_flags_only_the_real_series():
    """A sparse sample, so it proves no false positives — not recall (spec §8)."""
    path = Path(__file__).parent / "data" / "legacy_transactions_400.csv"
    groups: dict[str, list[RecurringRow]] = defaultdict(list)
    with path.open(encoding="utf-8") as f:
        for line in csv.DictReader(f):
            row = RecurringRow(uuid7(), dt.date.fromisoformat(line["date"][:10]), Decimal(line["amount"]), DETECTED)
            groups[normalise_merchant(line["merchant"])].append(row)
    flagged = {key for key, rows in groups.items() if any(detect_recurring(rows).values())}
    assert flagged == {"amznprime", "berliner verkehrsbetriebe bvg"}
