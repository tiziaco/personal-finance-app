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
        ([7, 7], True),  # weekly
        ([6, 6], True),  # weekly, lower edge
        ([8, 8], True),  # weekly, upper edge
        ([5, 5], False),  # just under weekly
        ([9, 9], False),  # just over weekly
        ([12, 12], True),  # weekly, one skipped period, lower edge
        ([16, 16], True),  # weekly, one skipped period, upper edge
        ([11, 11], False),  # just under weekly, one skipped period
        ([17, 17], False),  # just over weekly, one skipped period
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
        ([365], False),  # yearly needs three rows
        ([30], False),  # two rows are never a series
    ],
)
def test_cadences(gaps, expected):
    assert set(verdicts(series(gaps))) == {expected}


def test_one_skipped_period_still_fits():
    assert set(verdicts(series([30, 61, 30, 30]))) == {True}


def test_seeds_do_not_drift():
    """Clusters are anchored on fixed seeds, so a chain of near amounts does not pull its own ends together.

    10.00 -> 11.40 -> 12.80 each sit within the band of the next, but 12.80 is the most
    frequent amount, so it seeds the cluster and 11.40 joins it. 10.00 is 2.80 from that seed
    and stays alone. A running-median clusterer anchors on 10.00, drifts to 10.70 with 11.40,
    rejects 12.80 and marks every row False, which this test catches.
    """
    rows = [
        RecurringRow(uuid7(), START, Decimal("-10.00"), DETECTED),
        RecurringRow(uuid7(), START + dt.timedelta(days=30), Decimal("-11.40"), DETECTED),
        RecurringRow(uuid7(), START + dt.timedelta(days=60), Decimal("-12.80"), DETECTED),
        RecurringRow(uuid7(), START + dt.timedelta(days=90), Decimal("-12.80"), DETECTED),
    ]
    lone, drifted, *anchored = rows
    result = detect_recurring(rows)
    assert result[lone.id] is False
    assert result[drifted.id] is True
    assert [result[r.id] for r in anchored] == [True, True]


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
