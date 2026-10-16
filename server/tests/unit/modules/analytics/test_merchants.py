"""Merchants: spend and frequency per merchant, and how concentrated spending is."""

import datetime as dt
from dataclasses import fields
from decimal import Decimal

import pytest

from app.modules.analytics.domain.merchants import MerchantConcentration, MerchantSpend, merchant_breakdown
from app.modules.analytics.domain.period import resolve_period
from tests.unit.modules.analytics.rows import row

pytestmark = pytest.mark.unit

TODAY = dt.date(2026, 10, 16)

ROWS = [
    row("2026-01-01", "-10.00", merchant="Spotify"),
    row("2026-01-05", "-60.00", merchant="REWE"),
    row("2026-01-20", "-30.00", merchant="REWE"),
    row("2026-01-25", "-90.00", merchant="Landlord"),
    row("2026-01-31", "100.00", merchant="Employer"),  # income: not a merchant's spend
    row("2026-02-01", "-10.00", merchant="spotify "),  # same merchant, latest spelling
]

SPOTIFY = MerchantSpend(
    "spotify", Decimal("20.00"), 2, Decimal("10.00"), dt.date(2026, 1, 1), dt.date(2026, 2, 1), 10.0
)
REWE = MerchantSpend("REWE", Decimal("90.00"), 2, Decimal("45.00"), dt.date(2026, 1, 5), dt.date(2026, 1, 20), 45.0)
LANDLORD = MerchantSpend(
    "Landlord", Decimal("90.00"), 1, Decimal("90.00"), dt.date(2026, 1, 25), dt.date(2026, 1, 25), 45.0
)


def breakdown(rows=ROWS, top_n: int = 15, **period):
    return merchant_breakdown(
        rows,
        resolve_period(rows, TODAY, **period)
        if period
        else resolve_period(rows, TODAY, date_from=dt.date(2026, 1, 1), date_to=dt.date(2026, 2, 28)),
        top_n,
    )


def test_spellings_group_and_show_the_latest():
    result = breakdown()
    assert result.total_expenses == Decimal("200.00")
    assert result.top_by_spend == (LANDLORD, REWE, SPOTIFY)  # a tie at 90 breaks by name
    assert result.top_by_frequency == (REWE, SPOTIFY, LANDLORD)


def test_concentration_is_over_all_spending():
    c = breakdown().concentration
    assert (c.top_5_share_pct, c.top_10_share_pct) == (100.0, 100.0)
    assert c.herfindahl_index == 4150.0  # 10² + 45² + 45²
    assert c.unique_merchants == 3


def test_herfindahl_bounds():
    one = breakdown([row("2026-01-01", "-5.00", merchant="Only")]).concentration
    assert one.herfindahl_index == 10000.0
    ten = breakdown([row("2026-01-01", "-5.00", merchant=f"M{i}") for i in range(10)]).concentration
    assert ten.herfindahl_index == 1000.0
    assert merchant_breakdown([], None).concentration.herfindahl_index == 0.0


def test_top_n():
    assert len(breakdown(top_n=1).top_by_spend) == 1


def test_one_merchant_key_is_one_merchant_whatever_the_bank_printed():
    rows = [
        row("2026-01-01", "-10.00", merchant="PAYPAL *Spotify 4029357733"),
        row("2026-02-01", "-10.00", merchant="Spotify"),
        row("2026-02-03", "-5.00", merchant="Spotify Fan Shop", key="spotify fan shop"),
    ]
    result = breakdown(rows)
    assert [(m.merchant, m.count) for m in result.top_by_spend] == [("Spotify", 2), ("Spotify Fan Shop", 1)]
    assert result.concentration.unique_merchants == 2


def test_only_the_periods_rows_count():
    rows = [
        row("2026-06-10", "-50.00", merchant="June Shop"),
        row("2026-09-10", "-20.00", merchant="Sept Shop"),
    ]
    result = merchant_breakdown(rows, resolve_period(rows, TODAY, months=1))
    assert (result.date_from, result.date_to) == (dt.date(2026, 9, 1), dt.date(2026, 9, 30))
    assert result.total_expenses == Decimal("20.00")
    assert [m.merchant for m in result.top_by_spend] == ["Sept Shop"]
    assert result.concentration.unique_merchants == 1


def test_no_period_is_an_empty_breakdown():
    result = merchant_breakdown([], None)
    assert (result.date_from, result.date_to, result.top_by_spend) == (None, None, ())


def test_concentration_has_no_risk_band():
    assert "risk" not in {f.name for f in fields(MerchantConcentration)}
