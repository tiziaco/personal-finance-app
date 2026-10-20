"""The finance tools' arguments, as the model sends them. The user is never one of them."""

import datetime as dt
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.transaction import MAX_DATE, MIN_DATE


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
        description="The last N finished months, as the dashboard counts them (1 = the last finished month). "
        "Never includes the month in progress.",
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
