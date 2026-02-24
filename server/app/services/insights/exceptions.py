"""Insights service domain exceptions."""

from app.exceptions.base import ServiceError


class InsightsError(ServiceError):
    """Raised when insights generation or retrieval fails unexpectedly."""

    error_code = "INSIGHTS_ERROR"
    status_code = 500
