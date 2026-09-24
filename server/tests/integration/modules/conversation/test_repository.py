"""Integration tests for ConversationRepository — queries against the real test database."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.modules.account.models import User
from app.modules.conversation.models import Conversation
from app.modules.conversation.repository import ConversationRepository

pytestmark = pytest.mark.integration


@pytest.fixture
async def owner(db_session):
    """A user to own test conversations."""
    user = User(clerk_id="clerk_conv_repo_owner", org_id="test_org_123", email="conv_repo_owner@example.com")
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def other_user(db_session):
    """A second user, to prove per-user queries are scoped."""
    user = User(clerk_id="clerk_conv_repo_other", org_id="test_org_123", email="conv_repo_other@example.com")
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


async def _create(db_session, user_id, name=""):
    return await ConversationRepository.create(db_session, str(uuid.uuid4()), user_id, name=name)


class TestCreate:
    async def test_persists_the_row(self, db_session, owner):
        conv_id = str(uuid.uuid4())
        conv = await ConversationRepository.create(db_session, conv_id, owner.id, name="My Chat")
        assert (conv.id, conv.user_id, conv.name) == (conv_id, owner.id, "My Chat")
        assert conv.created_at is not None

    async def test_name_defaults_to_empty(self, db_session, owner):
        conv = await ConversationRepository.create(db_session, str(uuid.uuid4()), owner.id)
        assert conv.name == ""


class TestGetById:
    async def test_found(self, db_session, owner):
        conv = await _create(db_session, owner.id)
        assert (await ConversationRepository.get_by_id(db_session, conv.id)).id == conv.id

    async def test_missing_returns_none(self, db_session):
        assert await ConversationRepository.get_by_id(db_session, "nonexistent-conv-id") is None

    async def test_returns_soft_deleted_rows(self, db_session, owner):
        # get_user_conversation (dependencies.py) does its own deleted_at check.
        conv = await _create(db_session, owner.id)
        await ConversationRepository.soft_delete(db_session, conv.id)
        found = await ConversationRepository.get_by_id(db_session, conv.id)
        assert found is not None and found.deleted_at is not None


class TestListActiveForUser:
    async def test_oldest_first(self, db_session, owner):
        # Inserted out of created_at order, so heap order cannot pass for the ORDER BY.
        base = datetime(2026, 1, 1, tzinfo=UTC)
        rows = {
            k: Conversation(id=str(uuid.uuid4()), user_id=owner.id, created_at=base + timedelta(minutes=k))
            for k in (2, 0, 1)
        }
        db_session.add_all(rows.values())
        await db_session.flush()

        result = await ConversationRepository.list_active_for_user(db_session, owner.id)
        assert [c.id for c in result] == [rows[k].id for k in (0, 1, 2)]

    async def test_excludes_soft_deleted(self, db_session, owner):
        kept = await _create(db_session, owner.id)
        gone = await _create(db_session, owner.id)
        await ConversationRepository.soft_delete(db_session, gone.id)
        result = await ConversationRepository.list_active_for_user(db_session, owner.id)
        assert [c.id for c in result] == [kept.id]

    async def test_scoped_to_user(self, db_session, owner, other_user):
        mine = await _create(db_session, owner.id)
        await _create(db_session, other_user.id)
        result = await ConversationRepository.list_active_for_user(db_session, owner.id)
        assert [c.id for c in result] == [mine.id]


class TestUpdateName:
    async def test_sets_the_name(self, db_session, owner):
        conv = await _create(db_session, owner.id, name="Old")
        updated = await ConversationRepository.update_name(db_session, conv, "New")
        assert updated.name == "New"
        assert (await ConversationRepository.get_by_id(db_session, conv.id)).name == "New"


class TestSoftDelete:
    async def test_stamps_deleted_at(self, db_session, owner):
        conv = await _create(db_session, owner.id)
        assert await ConversationRepository.soft_delete(db_session, conv.id) is True
        assert (await ConversationRepository.get_by_id(db_session, conv.id)).is_deleted is True

    async def test_missing_returns_false(self, db_session):
        assert await ConversationRepository.soft_delete(db_session, "nonexistent-conv-id") is False


class TestSoftDeleteActiveForUser:
    async def test_returns_only_rows_it_deleted(self, db_session, owner):
        active = await _create(db_session, owner.id)
        already = await _create(db_session, owner.id)
        await ConversationRepository.soft_delete(db_session, already.id)

        assert await ConversationRepository.soft_delete_active_for_user(db_session, owner.id) == [active.id]
        assert await ConversationRepository.list_active_for_user(db_session, owner.id) == []

    async def test_scoped_to_user(self, db_session, owner, other_user):
        theirs = await _create(db_session, other_user.id)
        await ConversationRepository.soft_delete_active_for_user(db_session, owner.id)
        assert [c.id for c in await ConversationRepository.list_active_for_user(db_session, other_user.id)] == [
            theirs.id
        ]

    async def test_nothing_active_returns_empty(self, db_session, owner):
        assert await ConversationRepository.soft_delete_active_for_user(db_session, owner.id) == []


class TestBlankNamesForUser:
    async def test_blanks_soft_deleted_rows_too(self, db_session, owner):
        kept = await _create(db_session, owner.id, name="Kept")
        gone = await _create(db_session, owner.id, name="Gone")
        await ConversationRepository.soft_delete(db_session, gone.id)

        assert await ConversationRepository.blank_names_for_user(db_session, owner.id) == 2
        # No refresh(): the objects already in the session must see the UPDATE.
        assert (kept.name, gone.name) == ("", "")

    async def test_scoped_to_user(self, db_session, owner, other_user):
        theirs = await _create(db_session, other_user.id, name="Theirs")
        await ConversationRepository.blank_names_for_user(db_session, owner.id)
        await db_session.refresh(theirs)
        assert theirs.name == "Theirs"


class TestListIdsForUser:
    async def test_includes_soft_deleted_rows(self, db_session, owner):
        active = await _create(db_session, owner.id)
        gone = await _create(db_session, owner.id)
        await ConversationRepository.soft_delete(db_session, gone.id)

        ids = await ConversationRepository.list_ids_for_user(db_session, owner.id)

        assert sorted(ids) == sorted([active.id, gone.id])

    async def test_scoped_to_user(self, db_session, owner, other_user):
        await _create(db_session, other_user.id)
        mine = await _create(db_session, owner.id)

        assert await ConversationRepository.list_ids_for_user(db_session, owner.id) == [mine.id]

    async def test_none_returns_empty(self, db_session, owner):
        assert await ConversationRepository.list_ids_for_user(db_session, owner.id) == []
