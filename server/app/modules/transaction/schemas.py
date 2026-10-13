"""Transaction request/response schemas, and the category list."""

from enum import StrEnum

from pydantic import BaseModel, Field

# The category list: the only copy. Order is display order; slugs are what is
# stored and sent, labels what the web shows (served by GET /categories).
# Renaming a label touches nothing else. Renaming or removing a slug needs an
# UPDATE for the rows that hold it (docs/data-model/transaction.md).
CATEGORIES: list[tuple[str, str]] = [
    ("income", "Income"),
    ("salary", "Salary"),
    ("transportation", "Transportation"),
    ("household_utilities", "Household & Utilities"),
    ("tax_fines", "Tax & Fines"),
    ("food_groceries", "Food & Groceries"),
    ("food_delivery", "Food Delivery"),
    ("bars_restaurants", "Bars & Restaurants"),
    ("atm", "ATM"),
    ("insurances", "Insurances"),
    ("shopping", "Shopping"),
    ("education", "Education"),
    ("family_friends", "Family & Friends"),
    ("donations_charity", "Donations & Charity"),
    ("healthcare_drug_stores", "Healthcare & Drug Stores"),
    ("leisure_entertainment", "Leisure & Entertainment"),
    ("media_electronics", "Media & Electronics"),
    ("savings_investments", "Savings & Investments"),
    ("travel_holidays", "Travel & Holidays"),
    ("miscellaneous", "Miscellaneous"),
]

Category = StrEnum("Category", [(slug, slug) for slug, _ in CATEGORIES])

_LABELS = dict(CATEGORIES)


def category_label(category: str) -> str:
    """The display label for a slug; an unknown slug labels as itself."""
    return _LABELS.get(category, category)


class CategoryResponse(BaseModel):
    """One category, as the web lists it."""

    value: Category = Field(..., description="The category's slug, as stored and sent")
    label: str = Field(..., description="The category's display name")
