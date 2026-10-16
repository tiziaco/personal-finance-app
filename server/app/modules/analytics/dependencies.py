"""Analytics dependencies: the date range read from the query string."""

import datetime as dt
from typing import Annotated, Optional

from fastapi import Depends, Query

from app.modules.analytics.schemas import DateRange


def get_date_range(
    date_from: Optional[dt.date] = Query(None, description="On or after this day"),
    date_to: Optional[dt.date] = Query(None, description="On or before this day"),
    months: Optional[int] = Query(
        None, ge=1, le=120, description="The last N finished months; not with date_from/date_to"
    ),
) -> DateRange:
    """Inclusive, optional bounds, each between 1900 and 2100, or `months`; DateRange rejects the rest with a 422."""
    return DateRange(date_from=date_from, date_to=date_to, months=months)


AnalyticsRange = Annotated[DateRange, Depends(get_date_range)]
