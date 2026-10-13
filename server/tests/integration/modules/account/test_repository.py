"""Integration tests for UserRepository — CRUD against real test database."""

import pytest
from sqlalchemy.exc import IntegrityError
from uuid_utils.compat import uuid7

from app.modules.account.models import User
from app.modules.account.repository import UserRepository

pytestmark = pytest.mark.integration


@pytest.fixture
async def saved_user(db_session):
    """A committed user available for lookup tests."""
    user = User(
        clerk_id="clerk_repo_test_001",
        email="repo_test@example.com",
        first_name="Repo",
        last_name="Test",
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


class TestCreateUser:
    """Tests for UserRepository.create()."""

    async def test_create_returns_user_with_id(self, db_session):
        user = await UserRepository.create(
            db_session,
            clerk_id="clerk_create_001",
            email="create@example.com",
        )
        assert user.id is not None
        assert user.clerk_id == "clerk_create_001"
        assert user.email == "create@example.com"

    async def test_create_with_optional_fields(self, db_session):
        user = await UserRepository.create(
            db_session,
            clerk_id="clerk_create_002",
            email="create2@example.com",
            first_name="Alice",
            last_name="Smith",
            avatar_url="https://example.com/avatar.jpg",
            email_verified=True,
        )
        assert user.first_name == "Alice"
        assert user.last_name == "Smith"
        assert user.email_verified is True

    async def test_create_duplicate_clerk_id_raises(self, db_session, saved_user):
        with pytest.raises(IntegrityError):
            await UserRepository.create(
                db_session,
                clerk_id=saved_user.clerk_id,  # duplicate
                email="different@example.com",
            )

    async def test_create_allows_an_email_another_clerk_id_holds(self, db_session, saved_user):
        """Clerk owns email uniqueness; clerk_id is the identity (data-model/account.md D3)."""
        user = await UserRepository.create(
            db_session,
            clerk_id="clerk_unique_999",
            email=saved_user.email,
        )
        assert user.id != saved_user.id
        assert user.email == saved_user.email


class TestCreateOrGetUser:
    """Tests for UserRepository.create_or_get()."""

    async def test_no_existing_row_creates_user(self, db_session):
        user = await UserRepository.create_or_get(
            db_session,
            clerk_id="clerk_cog_001",
            email="cog@example.com",
        )
        assert user.id is not None
        assert user.clerk_id == "clerk_cog_001"

    async def test_clerk_id_race_returns_existing_user(self, db_session, saved_user):
        """A same-clerk_id conflict is a benign race — return the winner's row.

        Commit first so the "winner" row survives create_or_get's internal
        rollback, the way it would if a concurrent session had already
        committed it.
        """
        await db_session.commit()

        user = await UserRepository.create_or_get(
            db_session,
            clerk_id=saved_user.clerk_id,  # duplicate — simulates the losing request
            email="different@example.com",
        )
        assert user.id == saved_user.id
        assert user.email == saved_user.email  # untouched, not overwritten

    async def test_held_email_with_new_clerk_id_creates_a_second_user(self, db_session, saved_user):
        """Email is not unique (docs/data-model/account.md D3): a stale row holding it does not block a new account."""
        user = await UserRepository.create_or_get(
            db_session,
            clerk_id="clerk_cog_new_account",
            email=saved_user.email,
        )
        assert user.clerk_id == "clerk_cog_new_account"
        assert user.id != saved_user.id


class TestGetUser:
    """Tests for UserRepository.get_by_id/clerk_id."""

    async def test_get_by_id_found(self, db_session, saved_user):
        found = await UserRepository.get_by_id(db_session, saved_user.id)
        assert found is not None
        assert found.id == saved_user.id

    async def test_get_by_id_not_found(self, db_session):
        found = await UserRepository.get_by_id(db_session, uuid7())
        assert found is None

    async def test_get_by_clerk_id_found(self, db_session, saved_user):
        found = await UserRepository.get_by_clerk_id(db_session, saved_user.clerk_id)
        assert found is not None
        assert found.clerk_id == saved_user.clerk_id

    async def test_get_by_clerk_id_not_found(self, db_session):
        found = await UserRepository.get_by_clerk_id(db_session, "clerk_nonexistent")
        assert found is None


class TestUpdateUser:
    """Tests for UserRepository.update_from_clerk()."""

    async def test_update_email(self, db_session, saved_user):
        updated = await UserRepository.update_from_clerk(db_session, saved_user, email="new@example.com")
        assert updated.email == "new@example.com"

    async def test_update_partial_fields(self, db_session, saved_user):
        original_email = saved_user.email
        updated = await UserRepository.update_from_clerk(db_session, saved_user, first_name="UpdatedName")
        assert updated.first_name == "UpdatedName"
        assert updated.email == original_email  # unchanged

    async def test_update_none_fields_are_skipped(self, db_session, saved_user):
        original_first_name = saved_user.first_name
        updated = await UserRepository.update_from_clerk(db_session, saved_user, first_name=None)
        assert updated.first_name == original_first_name  # None → no change
