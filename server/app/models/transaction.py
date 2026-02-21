from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime
from sqlmodel import Field, Relationship

from app.models.base import BaseModel, SoftDeleteMixin

if TYPE_CHECKING:
    from app.models.user import User


class CategoryEnum(str, Enum):
    """Predefined spending categories for transaction classification."""

    INCOME = "Income"
    TRANSPORTATION = "Transportation"
    SALARY = "Salary"
    HOUSEHOLD_UTILITIES = "Household & Utilities"
    TAX_FINES = "Tax & Fines"
    MISCELLANEOUS = "Miscellaneous"
    FOOD_GROCERIES = "Food & Groceries"
    FOOD_DELIVERY = "Food Delivery"
    ATM = "ATM"
    INSURANCE = "Insurances"
    SHOPPING = "Shopping"
    BARS_RESTAURANTS = "Bars & Restaurants"
    EDUCATION = "Education"
    FAMILY_FRIENDS = "Family & Friends"
    DONATIONS_CHARITY = "Donations & Charity"
    HEALTHCARE_DRUG_STORES = "Healthcare & Drug Stores"
    LEISURE_ENTERTAINMENT = "Leisure & Entertainment"
    MEDIA_ELECTRONICS = "Media & Electronics"
    SAVINGS_INVESTMENTS = "Savings & Investments"
    TRAVEL_HOLIDAYS = "Travel & Holidays"


class Transaction(BaseModel, SoftDeleteMixin, table=True):
    """Financial transaction record owned by a user.

    confidence_score=1.0 signals a manually-entered (human-verified) transaction.
    Soft-deleted records (deleted_at IS NOT NULL) are excluded from all queries.
    """

    # Primary & Foreign Keys
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)

    # Core Transaction Data
    date: datetime = Field(sa_type=DateTime(timezone=True), index=True)
    merchant: str
    amount: float
    description: Optional[str] = None
    original_category: Optional[str] = None

    # Categorization
    category: CategoryEnum = Field(index=True)
    confidence_score: float = Field(ge=0.0, le=1.0)

    # Recurring Detection
    is_recurring: bool = Field(default=False)

    # Relationships
    user: Optional["User"] = Relationship(back_populates="transactions")
