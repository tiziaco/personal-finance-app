"""The finance tools' arguments, as the model sends them. The user is never one of them."""

import datetime as dt
from decimal import Decimal
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, WithJsonSchema, model_validator

from app.modules.transaction import MAX_DATE, MIN_DATE, Category


class PeriodArgs(BaseModel):
    """The period an analytics tool covers: the last `months` finished months, or ISO date bounds.

    Every analytics tool's arguments extend it. Whether the period holds any data is checked
    against the user's history when the tool runs (`to_date_range`), not here.
    """

    model_config = ConfigDict(extra="forbid")

    months: Optional[int] = Field(
        None,
        ge=1,
        le=120,
        description="The last N finished months, as the dashboard counts them: back from the latest finished month "
        "with transactions, which the turn context names (1 = that month). Never includes the month in progress.",
    )
    date_from: Optional[dt.date] = Field(
        None,
        ge=MIN_DATE,
        le=MAX_DATE,
        description="First day, inclusive (YYYY-MM-DD). Use date bounds for a named month, a range of months "
        "or the month in progress.",
    )
    date_to: Optional[dt.date] = Field(None, ge=MIN_DATE, le=MAX_DATE, description="Last day, inclusive (YYYY-MM-DD).")

    @model_validator(mode="after")
    def _one_kind_of_period(self) -> "PeriodArgs":
        dated = self.date_from is not None or self.date_to is not None
        if self.months is not None and dated:
            raise ValueError("give either months or date_from/date_to, not both")
        if self.months is None and not dated:
            raise ValueError("give a period: months (the last N finished months) or date_from/date_to")
        return self


class TopMerchantsArgs(PeriodArgs):
    """The period, and how many merchants to rank."""

    top_n: int = Field(10, ge=1, le=15, description="How many merchants to rank by spend.")


# Pydantic describes a Decimal as number-or-string with a lookahead regex `pattern`, and a model bound
# to that schema answers nothing. The model sends a JSON number; pydantic reads a float through its
# shortest repr (-0.1 is Decimal("-0.1")), so amounts stay exact server side.
Amount = Annotated[Decimal, WithJsonSchema({"type": "number"})]


class SearchArgs(BaseModel):
    """Filters for `search_transactions`; every one is optional and they all apply together."""

    model_config = ConfigDict(extra="forbid")

    merchant: Optional[Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)]] = Field(
        None, description='Part of the merchant name, any case ("lidl" finds "LIDL Berlin").'
    )
    date_from: Optional[dt.date] = Field(
        None, ge=MIN_DATE, le=MAX_DATE, description="First day, inclusive (YYYY-MM-DD)."
    )
    date_to: Optional[dt.date] = Field(None, ge=MIN_DATE, le=MAX_DATE, description="Last day, inclusive (YYYY-MM-DD).")
    categories: Optional[list[Category]] = Field(
        None, max_length=len(Category), description="Only these categories, by slug (the one in brackets)."
    )
    amount_min: Optional[Amount] = Field(
        None,
        description="Smallest signed amount in EUR: spending is negative, so -100 means spending up to 100 or any income.",
    )
    amount_max: Optional[Amount] = Field(
        None, description="Largest signed amount in EUR: -50 keeps spending of at least 50; 0 keeps only spending."
    )
    recurring_only: bool = Field(False, description="Only transactions marked recurring.")
    weekdays: Optional[list[Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]]] = Field(
        None, max_length=7, description="Only these days of the week."
    )
    group_by: Optional[Literal["month", "merchant", "category", "weekday"]] = Field(
        None, description="Also total the matches per month, merchant, category or weekday."
    )
    sample: Literal["largest", "recent"] = Field(
        "largest", description="Which matches to list: the largest by amount, or the most recent."
    )

    @model_validator(mode="after")
    def _ranges_are_ordered(self) -> "SearchArgs":
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError(
                f"date_from {self.date_from.isoformat()} is after date_to {self.date_to.isoformat()}; "
                "date_from must be the earlier day"
            )
        if self.amount_min is not None and self.amount_max is not None and self.amount_min > self.amount_max:
            raise ValueError(
                f"amount_min {self.amount_min} is above amount_max {self.amount_max}; amount_min must be the lower bound"
            )
        return self
