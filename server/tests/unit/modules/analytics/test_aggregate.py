"""The shared helpers every analysis stands on."""

import datetime as dt
from decimal import Decimal

import pytest

from app.modules.analytics.domain._aggregate import (
    add_months,
    average,
    cv,
    expenses,
    group_by,
    incomes,
    money,
    month_key,
    month_range,
    monthly_totals,
    pct_change,
    share_pct,
    spend,
    total_spend,
)
from tests.unit.modules.analytics.rows import row

pytestmark = pytest.mark.unit

D = dt.date


def test_money_quantises_and_drops_negative_zero():
    assert money(Decimal("1.005")) == Decimal("1.01")
    assert money(Decimal("2.675")) == Decimal("2.68")
    assert str(money(Decimal("-0.001"))) == "0.00"


def test_money_rounds_half_up():
    assert money(Decimal("0.125")) == Decimal("0.13")
    assert money(Decimal("0.525")) == Decimal("0.53")
    assert money(Decimal("-0.125")) == Decimal("-0.13")


def test_the_sign_decides_and_zero_is_neither():
    rows = [row("2026-01-01", "-5.00"), row("2026-01-02", "0.00"), row("2026-01-03", "7.00")]
    assert [r.amount for r in expenses(rows)] == [Decimal("-5.00")]
    assert [r.amount for r in incomes(rows)] == [Decimal("7.00")]
    assert spend(rows[0]) == Decimal("5.00")
    assert total_spend(expenses(rows)) == Decimal("5.00")


def test_months():
    assert month_key(D(2026, 9, 17)) == "2026-09"
    assert add_months(D(2026, 11, 1), 3) == D(2027, 2, 1)
    assert add_months(D(2026, 1, 1), -1) == D(2025, 12, 1)
    assert month_range(D(2025, 11, 30), D(2026, 2, 1)) == [
        D(2025, 11, 1),
        D(2025, 12, 1),
        D(2026, 1, 1),
        D(2026, 2, 1),
    ]
    assert month_range(D(2026, 3, 1), D(2026, 2, 1)) == []


def test_group_by_keeps_first_seen_order():
    rows = [
        row("2026-01-01", "-1", category="b"),
        row("2026-01-02", "-1", category="a"),
        row("2026-01-03", "-1", category="b"),
    ]
    groups = group_by(rows, lambda r: r.category)
    assert list(groups) == ["b", "a"]
    assert len(groups["b"]) == 2


def test_monthly_totals_zero_fill_missing_months():
    rows = [row("2026-01-05", "-10.00"), row("2026-03-01", "-4.50"), row("2026-03-02", "-0.50")]
    months = month_range(D(2026, 1, 1), D(2026, 3, 1))
    assert monthly_totals(rows, months, spend) == [Decimal("10.00"), Decimal("0.00"), Decimal("5.00")]


def test_ratios_never_divide_by_zero():
    assert pct_change(Decimal("0"), Decimal("10")) is None
    assert pct_change(Decimal("50"), Decimal("120")) == 140.0
    assert pct_change(Decimal("150"), Decimal("100")) == -33.33
    assert share_pct(Decimal("1"), Decimal("0")) == 0.0
    assert share_pct(Decimal("170"), Decimal("420")) == 40.48
    assert average(Decimal("10"), 0) == Decimal("0.00")
    assert average(Decimal("170"), 3) == Decimal("56.67")


def test_cv_is_population_stdev_over_mean():
    assert cv([Decimal("50"), Decimal("120")]) == 0.4118
    assert cv([Decimal("5")]) is None
    assert cv([Decimal("0"), Decimal("0")]) is None


def test_month_range_ending_in_december_9999_does_not_step_past_it():
    assert month_range(D(9999, 11, 1), D(9999, 12, 31)) == [D(9999, 11, 1), D(9999, 12, 1)]
