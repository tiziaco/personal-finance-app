"""Unit tests for model mixins.

These tests exercise pure in-memory behaviour — no database required.
"""

import uuid

import pytest

from app.models.base import UserOwnedMixin
from app.modules.account.models import User
from app.modules.conversation.models import Conversation

pytestmark = pytest.mark.unit

USER_ID = uuid.UUID("0199a8b0-0000-7000-8000-000000000001")


# ============================================================================
# SoftDeleteMixin (tested via Conversation)
# ============================================================================


class TestSoftDeleteMixin:
    """Tests for SoftDeleteMixin properties and methods."""

    def test_is_deleted_false_by_default(self):
        conv = Conversation(user_id=USER_ID)
        assert conv.is_deleted is False

    def test_deleted_at_none_by_default(self):
        conv = Conversation(user_id=USER_ID)
        assert conv.deleted_at is None

    def test_soft_delete_sets_deleted_at(self):
        conv = Conversation(user_id=USER_ID)
        conv.soft_delete()
        assert conv.deleted_at is not None

    def test_is_deleted_true_after_soft_delete(self):
        conv = Conversation(user_id=USER_ID)
        conv.soft_delete()
        assert conv.is_deleted is True

    def test_restore_clears_deleted_at(self):
        conv = Conversation(user_id=USER_ID)
        conv.soft_delete()
        conv.restore()
        assert conv.deleted_at is None

    def test_is_deleted_false_after_restore(self):
        conv = Conversation(user_id=USER_ID)
        conv.soft_delete()
        conv.restore()
        assert conv.is_deleted is False


# ============================================================================
# AnonymizableMixin (tested via User)
# ============================================================================


class TestAnonymizableMixin:
    """Tests for AnonymizableMixin properties and methods."""

    def test_is_anonymized_false_by_default(self):
        user = User(clerk_id="clerk_1", email="u@example.com")
        assert user.is_anonymized is False

    def test_anonymized_at_none_by_default(self):
        user = User(clerk_id="clerk_1", email="u@example.com")
        assert user.anonymized_at is None

    def test_mark_anonymized_sets_anonymized_at(self):
        user = User(clerk_id="clerk_1", email="u@example.com")
        user.mark_anonymized()
        assert user.anonymized_at is not None

    def test_is_anonymized_true_after_mark_anonymized(self):
        user = User(clerk_id="clerk_1", email="u@example.com")
        user.mark_anonymized()
        assert user.is_anonymized is True


# ============================================================================
# UserOwnedMixin
# ============================================================================


class TestUserOwnedMixin:
    """The column every user-owned table gets (architecture §9)."""

    def test_user_id_is_an_indexed_not_nullable_foreign_key_to_user(self):
        field = UserOwnedMixin.model_fields["user_id"]
        assert field.index is True
        assert field.nullable is False
        assert field.foreign_key == "user.id"

    def test_user_id_is_required(self):
        assert UserOwnedMixin.model_fields["user_id"].is_required()
