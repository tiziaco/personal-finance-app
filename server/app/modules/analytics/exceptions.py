"""Analytics module domain exceptions."""

from app.exceptions.base import ValidationError


class InvalidDateRangeError(ValidationError):
    """date_from falls after date_to."""

    error_code = "INVALID_DATE_RANGE"
