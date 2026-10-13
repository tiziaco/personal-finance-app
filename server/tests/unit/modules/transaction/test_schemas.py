"""The category list: one definition, slugs in display order."""

import pytest

from app.modules.transaction import CATEGORIES, Category, category_label
from app.modules.transaction.schemas import TransactionImport

pytestmark = pytest.mark.unit

SLUGS = [
    "income",
    "salary",
    "transportation",
    "household_utilities",
    "tax_fines",
    "food_groceries",
    "food_delivery",
    "bars_restaurants",
    "atm",
    "insurances",
    "shopping",
    "education",
    "family_friends",
    "donations_charity",
    "healthcare_drug_stores",
    "leisure_entertainment",
    "media_electronics",
    "savings_investments",
    "travel_holidays",
    "miscellaneous",
]


def test_categories_are_the_twenty_slugs_in_display_order():
    assert [slug for slug, _ in CATEGORIES] == SLUGS


def test_enum_is_built_from_the_list():
    assert [c.value for c in Category] == SLUGS


def test_labels_are_the_product_names():
    assert category_label("food_groceries") == "Food & Groceries"
    assert category_label("atm") == "ATM"


def test_an_unknown_slug_labels_as_itself():
    assert category_label("no_such_slug") == "no_such_slug"


@pytest.mark.parametrize("description", ["", "   "])
def test_an_import_with_a_blank_description_stores_none(description):
    row = TransactionImport(
        date="2026-03-03",
        merchant="Späti",
        amount="-4.50",
        description=description,
        category="food_groceries",
        confidence=0.9,
    )
    assert row.description is None
