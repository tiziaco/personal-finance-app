"""Insights module domain exceptions."""

from app.exceptions.base import ServiceUnavailableError


class InsightsUnavailableError(ServiceUnavailableError):
    """The model could not produce a valid set of insights; the stored set is untouched."""

    error_code = "INSIGHTS_UNAVAILABLE"
