"""Tests for app.modules.account.models."""

import pytest

from app.modules.account.models import Role, User

pytestmark = pytest.mark.unit


class TestRole:
    def test_all_roles_defined(self):
        assert Role.PROJECT_MANAGER == "project_manager"
        assert Role.REVIEWER == "reviewer"
        assert Role.APPROVER == "approver"
        assert Role.SUPPLIER == "supplier"

    def test_role_from_string(self):
        assert Role("project_manager") == Role.PROJECT_MANAGER

    def test_role_invalid_string_raises(self):
        with pytest.raises(ValueError):
            Role("admin")

    def test_role_is_str(self):
        assert isinstance(Role.PROJECT_MANAGER, str)


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
