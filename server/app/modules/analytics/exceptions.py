"""Analytics module domain exceptions."""

from app.exceptions.base import ValidationError


class InvalidDateRangeError(ValidationError):
    """A date bound is out of range, date_from falls after date_to, or months is out of range or given with a bound."""

    error_code = "INVALID_DATE_RANGE"
