"""Transaction request/response schemas, and the category list."""

import datetime as dt
import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, List, Literal, Optional

from pydantic import AfterValidator, BaseModel, Field, StringConstraints, field_validator, model_validator

from app.modules.transaction.domain.dates import MAX_DATE, MIN_DATE

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


class CategoryResponse(BaseModel):
    """One category, as the web lists it."""

    value: Category = Field(..., description="The category's slug, as stored and sent")
    label: str = Field(..., description="The category's display name")


Merchant = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
Amount = Annotated[Decimal, Field(max_digits=12, decimal_places=2, allow_inf_nan=False)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]


def _blank_to_none(value: Optional[str]) -> Optional[str]:
    return value or None


def _within_bounds(value: dt.date) -> dt.date:
    if not MIN_DATE <= value <= MAX_DATE:
        raise ValueError(f"must be between {MIN_DATE} and {MAX_DATE}")
    return value


# A date analytics covers: a hand-entered one outside the bounds would drop out of every analysis.
AnalysableDate = Annotated[dt.date, AfterValidator(_within_bounds)]


class TransactionCreate(BaseModel):
    """A transaction added by hand. Confidence is 1; no original category."""

    date: AnalysableDate = Field(..., description="The day the transaction happened")
    merchant: Merchant = Field(..., description="Who was paid, or who paid")
    amount: Amount = Field(..., description="Money out is negative, money in positive; a decimal string")
    description: Optional[Description] = Field(None, description="Free text; blank is stored as null")
    category: Category = Field(..., description="The category slug")
    is_recurring: bool = Field(False, description="Whether it recurs")
    allow_duplicate: bool = Field(
        False, description="Add even when an active transaction has the same date, merchant, amount and description"
    )

    _description = field_validator("description")(_blank_to_none)


class TransactionUpdate(BaseModel):
    """A partial edit. An omitted field is untouched; `description: null` clears it."""

    date: Optional[AnalysableDate] = Field(None, description="The day the transaction happened")
    merchant: Optional[Merchant] = Field(None, description="Who was paid, or who paid")
    amount: Optional[Amount] = Field(None, description="A decimal string")
    description: Optional[Description] = Field(None, description="Free text; null or blank clears it")
    category: Optional[Category] = Field(None, description="The category slug")
    is_recurring: Optional[bool] = Field(None, description="Whether it recurs")

    _description = field_validator("description")(_blank_to_none)

    @model_validator(mode="after")
    def _required_fields_are_not_null(self) -> "TransactionUpdate":
        for name in ("date", "merchant", "amount", "category", "is_recurring"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class TransactionImport(BaseModel):
    """A row written by the import and the seed: confidence and original category are its own."""

    date: dt.date
    merchant: Merchant
    amount: Amount
    description: Optional[Description] = None
    category: Category
    confidence: float = Field(..., ge=0, le=1)
    is_recurring: bool = Field(
        False, description="The importer's tick, kept as the user's; False lets the recurring rule decide"
    )
    original_category: Optional[Annotated[str, StringConstraints(max_length=255)]] = None

    _description = field_validator("description")(_blank_to_none)


class TransactionResponse(BaseModel):
    """A transaction as the API returns it."""

    id: uuid.UUID = Field(..., description="The transaction id")
    date: dt.date = Field(..., description="The day it happened")
    merchant: str = Field(..., description="Who was paid, or who paid")
    amount: Decimal = Field(..., description="Money out negative, money in positive; a decimal string")
    description: Optional[str] = Field(None, description="Free text")
    original_category: Optional[str] = Field(None, description="The bank's category, as imported")
    category: Category = Field(..., description="The category slug")
    confidence: float = Field(..., description="How sure the categoriser was, 0 to 1; 1 for a manual entry or edit")
    is_recurring: bool = Field(..., description="Whether it recurs")
    created_at: datetime = Field(..., description="When the row was created")
    updated_at: datetime = Field(..., description="When the row was last changed")

    model_config = {"from_attributes": True}


class AnalysisRow(BaseModel):
    """One active transaction as analytics reads it: the fields every calculation uses."""

    date: dt.date
    merchant: str
    merchant_key: str
    amount: Decimal
    category: str
    is_recurring: bool
    recurring_source: str = "detected"

    model_config = {"frozen": True}


TransactionOrdering = Literal["date", "-date", "amount", "-amount", "merchant", "-merchant"]


class TransactionFilters(BaseModel):
    """The list's filters. Every bound is inclusive; amounts are signed."""

    date_from: Optional[dt.date] = None
    date_to: Optional[dt.date] = None
    category: Optional[List[Category]] = None
    amount_min: Optional[Decimal] = None
    amount_max: Optional[Decimal] = None
    is_recurring: Optional[bool] = None


class TransactionListResponse(BaseModel):
    """One page of transactions."""

    items: List[TransactionResponse] = Field(..., description="The transactions on this page")
    total: int = Field(..., description="Active transactions matching the filters, across all pages")
    offset: int = Field(..., description="Rows skipped")
    limit: int = Field(..., description="Page size")


class BatchIds(BaseModel):
    """1–100 distinct transaction ids."""

    ids: List[uuid.UUID] = Field(..., min_length=1, max_length=100, description="Transaction ids, distinct")

    @field_validator("ids")
    @classmethod
    def _distinct(cls, ids: List[uuid.UUID]) -> List[uuid.UUID]:
        if len(set(ids)) != len(ids):
            raise ValueError("ids must be distinct")
        return ids


class BatchCategoryUpdate(BatchIds):
    """Give every listed transaction one category."""

    category: Category = Field(..., description="The category slug")


class BatchUpdateResponse(BaseModel):
    """How many transactions a batch changed."""

    updated: int = Field(..., description="Transactions changed")


class BatchDeleteResponse(BaseModel):
    """How many transactions a batch deleted."""

    deleted: int = Field(..., description="Transactions deleted")


class DeleteAllResponse(BaseModel):
    """How many transactions delete-all removed."""

    deleted: int = Field(..., description="Transactions permanently removed, earlier deleted ones included")
