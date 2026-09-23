"""Tests for app.schemas — Pydantic model validation, sanitization, serialization."""

import pytest

from app.schemas.base import ErrorResponse

pytestmark = pytest.mark.unit


class TestErrorResponse:
    """Tests for ErrorResponse schema."""

    def test_serialization_without_details(self):
        resp = ErrorResponse(
            error="NOT_FOUND",
            message="Resource not found",
            correlation_id="req-123",
        )
        data = resp.model_dump(exclude_none=True)
        assert "details" not in data
        assert data["error"] == "NOT_FOUND"

    def test_serialization_with_details(self):
        resp = ErrorResponse(
            error="VALIDATION_ERROR",
            message="Invalid input",
            correlation_id="req-456",
            details={"field": "email"},
        )
        data = resp.model_dump()
        assert data["details"] == {"field": "email"}
