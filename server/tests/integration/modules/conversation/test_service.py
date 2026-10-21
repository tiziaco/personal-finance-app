"""Integration tests for ConversationService — CRUD against real test database."""

from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from uuid_utils.compat import uuid7

from app.modules.account.models import User
from app.modules.conversation.exceptions import ConversationNotFoundError
from app.modules.conversation.service import ConversationService

pytestmark = pytest.mark.integration


@pytest.fixture
async def db_user(db_session):
    """A user to own test conversations."""
    user = User(
        clerk_id="clerk_conv_owner_001",
        email="conv_owner@example.com",
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def saved_conversation(db_session, db_user):
    """A conversation created via the service."""
    return await ConversationService.create_conversation(db_session, db_user.id, name="Existing Conversation")


class TestCreateConversation:
    """Tests for ConversationService.create_conversation()."""

    async def test_creates_with_generated_id(self, db_session, db_user):
        conv = await ConversationService.create_conversation(db_session, db_user.id, name="My Chat")
        assert conv.id.version == 7
        assert conv.user_id == db_user.id
        assert conv.name == "My Chat"

    async def test_creates_with_empty_name_by_default(self, db_session, db_user):
        conv = await ConversationService.create_conversation(db_session, db_user.id)
        assert conv.name == ""

    async def test_created_at_is_set(self, db_session, db_user):
        conv = await ConversationService.create_conversation(db_session, db_user.id)
        assert conv.created_at is not None


class TestGetConversation:
    """Tests for ConversationService.get_conversation()."""

    async def test_get_found(self, db_session, saved_conversation):
        result = await ConversationService.get_conversation(db_session, saved_conversation.id)
        assert result is not None
        assert result.id == saved_conversation.id

    async def test_get_not_found_returns_none(self, db_session):
        result = await ConversationService.get_conversation(db_session, uuid7())
        assert result is None


class TestGetUserConversations:
    """Tests for ConversationService.get_user_conversations()."""

    async def test_empty_list_for_new_user(self, db_session, db_user):
        result = await ConversationService.get_user_conversations(db_session, db_user.id)
        assert result == []

    async def test_returns_all_user_conversations(self, db_session, db_user):
        for i in range(3):
            await ConversationService.create_conversation(db_session, db_user.id, name=f"Chat {i}")

        result = await ConversationService.get_user_conversations(db_session, db_user.id)
        assert len(result) == 3

    async def test_does_not_return_other_users_conversations(self, db_session, db_user):
        # Create a second user with their own conversation
        other_user = User(clerk_id="clerk_other_002", email="other@example.com")
        db_session.add(other_user)
        await db_session.flush()
        await db_session.refresh(other_user)

        await ConversationService.create_conversation(db_session, other_user.id, name="Other's Chat")
        await ConversationService.create_conversation(db_session, db_user.id, name="My Chat")

        result = await ConversationService.get_user_conversations(db_session, db_user.id)
        assert len(result) == 1
        assert result[0].user_id == db_user.id


class TestUpdateConversationName:
    """Tests for ConversationService.update_conversation_name()."""

    async def test_update_name_success(self, db_session, saved_conversation):
        updated = await ConversationService.update_conversation_name(db_session, saved_conversation.id, "New Name")
        assert updated.name == "New Name"
        assert updated.id == saved_conversation.id

    async def test_update_nonexistent_raises(self, db_session):
        with pytest.raises(ConversationNotFoundError):
            await ConversationService.update_conversation_name(db_session, uuid7(), "New Name")


class TestSoftDeleteConversation:
    """Tests for ConversationService.soft_delete_conversation()."""

    async def test_soft_delete_returns_true(self, db_session, saved_conversation):
        result = await ConversationService.soft_delete_conversation(db_session, saved_conversation.id)
        assert result is True

    async def test_soft_delete_sets_deleted_at(self, db_session, saved_conversation):
        await ConversationService.soft_delete_conversation(db_session, saved_conversation.id)
        conv = await ConversationService.get_conversation(db_session, saved_conversation.id)
        assert conv is not None
        assert conv.is_deleted is True
        assert conv.deleted_at is not None

    async def test_soft_delete_nonexistent_returns_false(self, db_session):
        result = await ConversationService.soft_delete_conversation(db_session, uuid7())
        assert result is False

    async def test_get_user_conversations_excludes_soft_deleted(self, db_session, db_user):
        conv = await ConversationService.create_conversation(db_session, db_user.id, name="To Be Deleted")
        await ConversationService.soft_delete_conversation(db_session, conv.id)

        result = await ConversationService.get_user_conversations(db_session, db_user.id)
        assert all(c.id != conv.id for c in result)


class TestSoftDeleteAllUserConversations:
    """Tests for ConversationService.soft_delete_all_user_conversations()."""

    async def test_returns_list_of_active_conversation_ids(self, db_session, db_user):
        ids = [(await ConversationService.create_conversation(db_session, db_user.id)).id for _ in range(3)]

        returned_ids = await ConversationService.soft_delete_all_user_conversations(db_session, db_user.id)
        assert sorted(returned_ids) == sorted(ids)

    async def test_all_conversations_marked_soft_deleted(self, db_session, db_user):
        for _ in range(2):
            await ConversationService.create_conversation(db_session, db_user.id)

        await ConversationService.soft_delete_all_user_conversations(db_session, db_user.id)

        remaining = await ConversationService.get_user_conversations(db_session, db_user.id)
        assert remaining == []

    async def test_already_deleted_not_included_in_result(self, db_session, db_user):
        active = await ConversationService.create_conversation(db_session, db_user.id)
        already_deleted = await ConversationService.create_conversation(db_session, db_user.id)
        await ConversationService.soft_delete_conversation(db_session, already_deleted.id)

        returned_ids = await ConversationService.soft_delete_all_user_conversations(db_session, db_user.id)
        assert active.id in returned_ids
        assert already_deleted.id not in returned_ids

    async def test_returns_empty_list_when_no_active_conversations(self, db_session, db_user):
        returned_ids = await ConversationService.soft_delete_all_user_conversations(db_session, db_user.id)
        assert returned_ids == []


async def test_blank_all_user_conversation_names_touches_deleted_rows_too(db_session, test_user):
    service = ConversationService()
    kept = await service.create_conversation(db_session, test_user.id, name="Kept")
    gone = await service.create_conversation(db_session, test_user.id, name="Gone")
    await service.soft_delete_conversation(db_session, gone.id)

    assert await service.blank_all_user_conversation_names(db_session, test_user.id) == 2

    await db_session.refresh(kept)
    await db_session.refresh(gone)
    assert (kept.name, gone.name) == ("", "")


class TestGenerateTitle:
    """`generate_title` reads the agent's thread and asks the model for a title from its first exchange."""

    @pytest.fixture
    async def untitled(self, db_session, db_user):
        return await ConversationService.create_conversation(db_session, db_user.id)

    @staticmethod
    async def _thread(agent, conversation, *messages):
        await agent.graph.aupdate_state(
            {"configurable": {"thread_id": str(conversation.id)}}, {"messages": list(messages)}
        )

    async def test_the_title_is_written_from_the_first_answered_exchange(self, db_session, untitled, agent):
        await self._thread(
            agent,
            untitled,
            HumanMessage("a question the user stopped"),
            HumanMessage("How much on groceries?"),
            AIMessage("You spent 312 EUR."),
            HumanMessage("And on rent?"),
            AIMessage("800 EUR."),
        )
        model = AsyncMock(return_value="Grocery spending")

        with patch("app.modules.conversation.service.generate_title", model):
            conversation = await ConversationService.generate_title(db_session, untitled, agent)

        model.assert_awaited_once_with("How much on groceries?", "You spent 312 EUR.", untitled.id, untitled.user_id)
        assert conversation.name == "Grocery spending"

    @pytest.mark.parametrize("messages", [[], [HumanMessage("Hello")]], ids=["empty thread", "no reply yet"])
    async def test_before_any_reply_the_model_is_not_asked(self, db_session, untitled, agent, messages):
        if messages:
            await self._thread(agent, untitled, *messages)
        model = AsyncMock(return_value="Never")

        with patch("app.modules.conversation.service.generate_title", model):
            conversation = await ConversationService.generate_title(db_session, untitled, agent)

        model.assert_not_awaited()
        assert conversation.name == ""

    async def test_a_failing_model_leaves_the_conversation_untitled_and_is_logged(self, db_session, untitled, agent):
        await self._thread(agent, untitled, HumanMessage("Q"), AIMessage("A"))

        with (
            patch("app.modules.conversation.service.generate_title", AsyncMock(side_effect=RuntimeError("down"))),
            patch("app.modules.conversation.service.logger") as log,
        ):
            conversation = await ConversationService.generate_title(db_session, untitled, agent)

        assert conversation.name == ""
        assert log.exception.call_args.args[0] == "conversation_title_generation_failed"
