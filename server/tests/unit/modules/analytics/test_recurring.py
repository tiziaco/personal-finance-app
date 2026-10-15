"""Recurring: what the stored flag marks, its monthly cost, and unflagged small regulars."""

from decimal import Decimal

import pytest

from app.modules.analytics.domain.recurring import HiddenSubscription, RecurringMerchant, recurring_analysis
from tests.unit.modules.analytics.rows import row

pytestmark = pytest.mark.unit

ROWS = [
    row("2026-01-01", "-10.00", merchant="Netflix", recurring=True),
    row("2026-01-02", "-3.00", merchant="Coffee"),
    row("2026-01-09", "-3.00", merchant="Coffee"),
    row("2026-01-15", "-900.00", merchant="Landlord", recurring=True),
    row("2026-01-16", "-3.00", merchant="coffee"),
    row("2026-01-20", "-100.00", merchant="IKEA"),
    row("2026-01-27", "2000.00", merchant="Employer", recurring=True),  # income: ignored
    row("2026-02-01", "-10.00", merchant="Netflix", recurring=True),
    row("2026-02-02", "-3.50", merchant="Coffee"),
    row("2026-02-09", "-3.50", merchant="Coffee"),
    row("2026-02-15", "-900.00", merchant="Landlord", recurring=True),
    row("2026-02-16", "-3.50", merchant="Coffee"),
    row("2026-03-01", "-12.00", merchant="Netflix", recurring=True),
]


def test_flagged_spend_and_its_share():
    result = recurring_analysis(ROWS)
    assert result.total_expenses == Decimal("1951.50")
    assert result.recurring_total == Decimal("1832.00")
    assert result.recurring_count == 5
    assert result.amount_share_pct == 93.88
    assert result.count_share_pct == 41.67  # 5 of 12 expenses


def test_monthly_recurring_cost_is_a_run_rate():
    result = recurring_analysis(ROWS)
    assert result.merchants == (
        RecurringMerchant("Landlord", 2, 2, Decimal("900.00"), Decimal("900.00")),
        RecurringMerchant("Netflix", 3, 3, Decimal("10.00"), Decimal("10.00")),  # median, not mean
    )
    assert result.monthly_recurring_cost == Decimal("910.00")


def test_hidden_subscriptions_are_unflagged_small_and_frequent():
    result = recurring_analysis(ROWS)
    assert result.hidden_subscriptions == (HiddenSubscription("Coffee", 6, 2, Decimal("3.25"), 3.0),)


def test_empty_input():
    result = recurring_analysis([])
    assert result.recurring_total == Decimal("0.00")
    assert result.amount_share_pct == 0.0
    assert result.merchants == () and result.hidden_subscriptions == ()
