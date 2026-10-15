"""Categories: ranked spend, frequency, and per-category growth across months."""

from decimal import Decimal

import pytest

from app.modules.analytics.domain.categories import CategorySpend, CategoryTrend, category_breakdown
from tests.unit.modules.analytics.rows import row

pytestmark = pytest.mark.unit

ROWS = [
    row("2026-01-03", "-50.00", category="food_groceries"),
    row("2026-01-10", "-150.00", category="household_utilities"),
    row("2026-02-03", "-100.00", category="food_groceries"),
    row("2026-02-10", "-100.00", category="household_utilities"),
    row("2026-02-12", "-20.00", category="food_groceries"),
    row("2026-02-20", "500.00", category="salary"),  # income: never a category's spend
]

FOOD = CategorySpend("food_groceries", Decimal("170.00"), 3, Decimal("56.67"), 40.48)
HOUSE = CategorySpend("household_utilities", Decimal("250.00"), 2, Decimal("125.00"), 59.52)


def test_ranked_by_spend_and_by_frequency():
    result = category_breakdown(ROWS)
    assert result.total_expenses == Decimal("420.00")
    assert result.top_categories == (HOUSE, FOOD)
    assert result.by_frequency == (FOOD, HOUSE)


def test_top_n_cuts_both_rankings():
    result = category_breakdown(ROWS, top_n=1)
    assert result.top_categories == (HOUSE,)
    assert result.by_frequency == (FOOD,)


def test_growth_from_first_to_last_month_with_spend():
    result = category_breakdown(ROWS)
    assert result.top_growing == (CategoryTrend("food_groceries", Decimal("50.00"), Decimal("120.00"), 140.0, 0.4118),)
    assert result.top_declining == (
        CategoryTrend("household_utilities", Decimal("150.00"), Decimal("100.00"), -33.33, 0.2),
    )


def test_a_category_with_one_month_has_no_trend():
    result = category_breakdown([row("2026-01-03", "-50.00", category="food_groceries")])
    assert result.top_growing == () and result.top_declining == ()


def test_empty_input():
    result = category_breakdown([])
    assert result.total_expenses == Decimal("0.00")
    assert result.top_categories == ()
