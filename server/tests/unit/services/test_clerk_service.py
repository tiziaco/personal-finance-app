"""Tests for app.services.clerk.service — Clerk API error mapping and email extraction."""

from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from clerk_backend_api import ClerkErrors

from app.services.clerk.exceptions import (
    ClerkAPIError,
    ClerkAuthenticationError,
    ClerkRateLimitError,
    ClerkUserNotFoundError,
)
from app.services.clerk.service import ClerkService

pytestmark = pytest.mark.unit


@pytest.fixture
def service():
    """Fresh ClerkService with mocked client."""
    svc = ClerkService()
    svc._client = MagicMock()
    return svc


def _make_clerk_error(status_code: int) -> ClerkErrors:
    """Create a ClerkErrors with a fake raw_response."""
    err = ClerkErrors.__new__(ClerkErrors)
    object.__setattr__(err, "message", f"HTTP {status_code}")
    object.__setattr__(err, "raw_response", MagicMock(status_code=status_code))
    return err


class TestGetUser:
    """Tests for ClerkService.get_user()."""

    def test_success(self, service):
        mock_user = MagicMock()
        service._client.users.get.return_value = mock_user

        result = service.get_user("user_123")

        assert result == mock_user
        service._client.users.get.assert_called_once_with(user_id="user_123")

    def test_404_raises_not_found(self, service):
        service._client.users.get.side_effect = _make_clerk_error(404)

        with pytest.raises(ClerkUserNotFoundError):
            service.get_user("user_missing")

    def test_401_raises_authentication_error(self, service):
        service._client.users.get.side_effect = _make_clerk_error(401)

        with pytest.raises(ClerkAuthenticationError):
            service.get_user("user_123")

    def test_429_raises_rate_limit_error(self, service):
        service._client.users.get.side_effect = _make_clerk_error(429)

        with pytest.raises(ClerkRateLimitError):
            service.get_user("user_123")

    def test_500_raises_generic_api_error(self, service):
        service._client.users.get.side_effect = _make_clerk_error(500)

        with pytest.raises(ClerkAPIError):
            service.get_user("user_123")

    def test_unexpected_exception_raises_api_error(self, service):
        service._client.users.get.side_effect = RuntimeError("network down")

        with pytest.raises(ClerkAPIError, match="Unexpected error"):
            service.get_user("user_123")


class TestGetPrimaryEmail:
    """Tests for ClerkService.get_primary_email()."""

    def test_primary_email_found(self, service):
        email_obj = MagicMock()
        email_obj.id = "email_primary"
        email_obj.email_address = "primary@example.com"

        clerk_user = MagicMock()
        clerk_user.email_addresses = [email_obj]
        clerk_user.primary_email_address_id = "email_primary"

        assert service.get_primary_email(clerk_user) == "primary@example.com"

    def test_fallback_to_first_email(self, service):
        primary = MagicMock()
        primary.id = "email_primary"
        primary.email_address = "primary@example.com"

        other = MagicMock()
        other.id = "email_other"
        other.email_address = "other@example.com"

        clerk_user = MagicMock()
        clerk_user.email_addresses = [other, primary]
        clerk_user.primary_email_address_id = "email_nonexistent"

        assert service.get_primary_email(clerk_user) == "other@example.com"

    def test_no_emails_returns_none(self, service):
        clerk_user = MagicMock()
        clerk_user.email_addresses = []

        assert service.get_primary_email(clerk_user) is None
