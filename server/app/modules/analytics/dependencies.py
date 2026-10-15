"""Analytics dependencies: the date range read from the query string."""

import datetime as dt
from typing import Annotated, Optional

from fastapi import Depends, Query

from app.modules.analytics.exceptions import InvalidDateRangeError
from app.modules.analytics.schemas import DateRange

MIN_DATE = dt.date(1900, 1, 1)
MAX_DATE = dt.date(2100, 12, 31)


def get_date_range(
    date_from: Optional[dt.date] = Query(None, description="On or after this day"),
    date_to: Optional[dt.date] = Query(None, description="On or before this day"),
) -> DateRange:
    """Inclusive, optional bounds, each between 1900 and 2100. A start after the end is a 422."""
    for name, value in (("date_from", date_from), ("date_to", date_to)):
        if value is not None and not MIN_DATE <= value <= MAX_DATE:
            raise InvalidDateRangeError(
                f"{name} must be between {MIN_DATE} and {MAX_DATE}", date_from=str(date_from), date_to=str(date_to)
            )
    if date_from and date_to and date_from > date_to:
        raise InvalidDateRangeError("date_from is after date_to", date_from=str(date_from), date_to=str(date_to))
    return DateRange(date_from=date_from, date_to=date_to)


AnalyticsRange = Annotated[DateRange, Depends(get_date_range)]
