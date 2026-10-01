"""Tests for app.modules.account.schemas."""

from datetime import UTC, datetime

import pytest
from uuid_utils.compat import uuid7

from app.modules.account.schemas import UserResponse

pytestmark = pytest.mark.unit


class TestUserResponse:
    """Tests for UserResponse schema."""

    def test_valid_user_response(self):
        resp = UserResponse(
            id=uuid7(),
            clerk_id="user_abc",
            email="test@example.com",
            first_name="Alice",
            last_name="Smith",
            avatar_url=None,
            created_at=datetime.now(UTC),
        )
        assert resp.email == "test@example.com"

    def test_optional_fields_default_to_none(self):
        resp = UserResponse(
            id=uuid7(),
            clerk_id="user_abc",
            email="test@example.com",
            created_at=datetime.now(UTC),
        )
        assert resp.first_name is None
        assert resp.last_name is None
        assert resp.avatar_url is None
