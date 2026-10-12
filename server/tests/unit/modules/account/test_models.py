"""Tests for app.modules.account.models."""

import uuid

import pytest

from app.modules.account.models import User

pytestmark = pytest.mark.unit


class TestUserAnonymizeUser:
    """Tests for User.anonymize_user() GDPR anonymization method."""

    @pytest.fixture
    def full_user(self):
        return User(
            clerk_id="clerk_abc123",
            email="alice@example.com",
            first_name="Alice",
            last_name="Smith",
            avatar_url="https://example.com/avatar.jpg",
            email_verified=True,
        )

    def test_clerk_id_replaced(self, full_user):
        full_user.anonymize_user()
        assert full_user.clerk_id != "clerk_abc123"
        assert full_user.clerk_id.startswith("deleted_user_")

    def test_email_replaced_with_anonymized_local(self, full_user):
        full_user.anonymize_user()
        assert full_user.email.endswith("@anonymized.local")

    def test_first_name_cleared(self, full_user):
        full_user.anonymize_user()
        assert full_user.first_name is None

    def test_last_name_cleared(self, full_user):
        full_user.anonymize_user()
        assert full_user.last_name is None

    def test_avatar_url_cleared(self, full_user):
        full_user.anonymize_user()
        assert full_user.avatar_url is None

    def test_email_verified_set_to_false(self, full_user):
        full_user.anonymize_user()
        assert full_user.email_verified is False

    def test_is_anonymized_true_after_call(self, full_user):
        full_user.anonymize_user()
        assert full_user.is_anonymized is True

    def test_two_users_created_in_the_same_minute_do_not_collide(self):
        """A v7 id's first 8 hex digits are its timestamp: constant for ~65 s, so a prefix is not unique."""
        a = User(id=uuid.UUID("0199a8b0-1111-7000-8000-000000000001"), clerk_id="clerk_a", email="a@example.com")
        b = User(id=uuid.UUID("0199a8b0-2222-7000-8000-000000000002"), clerk_id="clerk_b", email="b@example.com")

        a.anonymize_user()
        b.anonymize_user()

        assert a.clerk_id != b.clerk_id
        assert a.email != b.email
