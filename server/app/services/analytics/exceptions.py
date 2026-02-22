"""Analytics service domain exceptions."""

from app.exceptions.base import ServiceError


class AnalyticsError(ServiceError):
    """Raised when analytics computation fails unexpectedly."""

    error_code = "ANALYTICS_ERROR"
    status_code = 500
