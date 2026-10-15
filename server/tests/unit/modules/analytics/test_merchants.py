"""Merchants: spend and frequency per merchant, and how concentrated spending is."""

import datetime as dt
from decimal import Decimal

import pytest

from app.modules.analytics.domain.merchants import MerchantSpend, merchant_breakdown
from tests.unit.modules.analytics.rows import row

pytestmark = pytest.mark.unit

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


def test_spellings_group_and_show_the_latest():
    result = merchant_breakdown(ROWS)
    assert result.total_expenses == Decimal("200.00")
    assert result.top_by_spend == (LANDLORD, REWE, SPOTIFY)  # a tie at 90 breaks by name
    assert result.top_by_frequency == (REWE, SPOTIFY, LANDLORD)


def test_concentration_is_over_all_spending():
    c = merchant_breakdown(ROWS).concentration
    assert (c.top_5_share_pct, c.top_10_share_pct) == (100.0, 100.0)
    assert c.herfindahl_index == 4150.0  # 10² + 45² + 45²
    assert c.risk == "high"
    assert c.unique_merchants == 3


def test_herfindahl_bounds():
    one = merchant_breakdown([row("2026-01-01", "-5.00", merchant="Only")]).concentration
    assert one.herfindahl_index == 10000.0
    ten = merchant_breakdown([row("2026-01-01", "-5.00", merchant=f"M{i}") for i in range(10)]).concentration
    assert ten.herfindahl_index == 1000.0
    assert ten.risk == "low"
    assert merchant_breakdown([]).concentration.herfindahl_index == 0.0


def test_top_n():
    assert len(merchant_breakdown(ROWS, top_n=1).top_by_spend) == 1
