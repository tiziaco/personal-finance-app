"""Integration tests for conversation CRUD API endpoints."""

import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import update
from uuid_utils.compat import uuid7

from app.modules.conversation.models import Conversation

pytestmark = pytest.mark.integration


@pytest.fixture
async def user_conversation(db_session, test_user):
    """An existing conversation owned by test_user."""
    conv = Conversation(
        user_id=test_user.id,
        name="Existing Chat",
    )
    db_session.add(conv)
    await db_session.flush()
    await db_session.refresh(conv)
    return conv


class TestCreateConversation:
    """Tests for POST /api/v1/conversation/conversation"""

    async def test_unauthenticated_returns_401(self, client):
        response = await client.post("/api/v1/conversation/conversation")
        assert response.status_code == 401

    async def test_creates_conversation_returns_200(self, authenticated_client):
        response = await authenticated_client.post("/api/v1/conversation/conversation")
        assert response.status_code == 200

    async def test_response_has_conversation_id(self, authenticated_client):
        response = await authenticated_client.post("/api/v1/conversation/conversation")
        data = response.json()
        assert "conversation_id" in data
        assert uuid.UUID(data["conversation_id"]).version == 7

    async def test_response_schema(self, authenticated_client):
        response = await authenticated_client.post("/api/v1/conversation/conversation")
        data = response.json()
        assert "conversation_id" in data
        assert "name" in data
        assert "created_at" in data


class TestListConversations:
    """Tests for GET /api/v1/conversation/conversations"""

    async def test_unauthenticated_returns_401(self, client):
        response = await client.get("/api/v1/conversation/conversations")
        assert response.status_code == 401

    async def test_empty_list_for_new_user(self, authenticated_client):
        response = await authenticated_client.get("/api/v1/conversation/conversations")
        assert response.status_code == 200
        assert response.json() == []

    async def test_returns_user_conversations(self, authenticated_client, user_conversation):
        response = await authenticated_client.get("/api/v1/conversation/conversations")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["conversation_id"] == str(user_conversation.id)


class TestRenameConversation:
    """Tests for PATCH /api/v1/conversation/conversation/{id}/name"""

    async def test_unauthenticated_returns_401(self, client, user_conversation):
        response = await client.patch(
            f"/api/v1/conversation/conversation/{user_conversation.id}/name",
            data={"name": "New Name"},
        )
        assert response.status_code == 401

    async def test_rename_succeeds(self, authenticated_client, user_conversation):
        response = await authenticated_client.patch(
            f"/api/v1/conversation/conversation/{user_conversation.id}/name",
            data={"name": "Renamed Chat"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Renamed Chat"
        assert data["conversation_id"] == str(user_conversation.id)

    @pytest.mark.parametrize("name", ["O'Brien's trip", "Anne & <Marie>"])
    async def test_rename_stores_the_name_verbatim(self, authenticated_client, user_conversation, db_session, name):
        """Escaping is the renderer's job; renaming twice must not compound it."""
        url = f"/api/v1/conversation/conversation/{user_conversation.id}/name"

        for _ in range(2):
            response = await authenticated_client.patch(url, data={"name": name})
            assert response.status_code == 200
            assert response.json()["name"] == name
            await db_session.refresh(user_conversation)
            assert user_conversation.name == name

        listed = await authenticated_client.get("/api/v1/conversation/conversations")
        assert listed.json()[0]["name"] == name

    async def test_rename_drops_null_bytes(self, authenticated_client, user_conversation):
        """Postgres text columns reject NUL outright."""
        response = await authenticated_client.patch(
            f"/api/v1/conversation/conversation/{user_conversation.id}/name",
            data={"name": "Trip\0 plan"},
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Trip plan"

    async def test_rename_accepts_100_chars(self, authenticated_client, user_conversation):
        response = await authenticated_client.patch(
            f"/api/v1/conversation/conversation/{user_conversation.id}/name",
            data={"name": "x" * 100},
        )
        assert response.status_code == 200

    async def test_rename_over_100_chars_is_rejected_not_stored(
        self, authenticated_client, user_conversation, db_session
    ):
        """Bounded on input: an over-long name stored, then refused by the response model, was a 500."""
        response = await authenticated_client.patch(
            f"/api/v1/conversation/conversation/{user_conversation.id}/name",
            data={"name": "x" * 101},
        )
        assert response.status_code == 422
        await db_session.refresh(user_conversation)
        assert user_conversation.name == "Existing Chat"

    async def test_rename_nonexistent_returns_404(self, authenticated_client):
        response = await authenticated_client.patch(
            f"/api/v1/conversation/conversation/{uuid7()}/name",
            data={"name": "New Name"},
        )
        assert response.status_code == 404

    async def test_rename_other_users_conversation_returns_404(self, db_session, authenticated_client):
        from app.modules.account.models import User

        other_user = User(clerk_id="clerk_other_conv", email="other_conv@example.com")
        db_session.add(other_user)
        await db_session.flush()
        await db_session.refresh(other_user)

        other_conv = Conversation(
            user_id=other_user.id,
            name="Other's Chat",
        )
        db_session.add(other_conv)
        await db_session.flush()

        response = await authenticated_client.patch(
            f"/api/v1/conversation/conversation/{other_conv.id}/name",
            data={"name": "Hijacked"},
        )
        assert response.status_code == 404


class TestDeleteConversation:
    """Tests for DELETE /api/v1/conversation/conversation/{id}"""

    async def test_unauthenticated_returns_401(self, client, user_conversation):
        response = await client.delete(f"/api/v1/conversation/conversation/{user_conversation.id}")
        assert response.status_code == 401

    async def test_delete_succeeds(self, authenticated_client_with_agent, user_conversation, stub_checkpoint_deletion):
        response = await authenticated_client_with_agent.delete(
            f"/api/v1/conversation/conversation/{user_conversation.id}"
        )
        assert response.status_code == 204

    async def test_delete_nonexistent_returns_404(self, authenticated_client_with_agent):
        response = await authenticated_client_with_agent.delete(f"/api/v1/conversation/conversation/{uuid7()}")
        assert response.status_code == 404

    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("patch", "/api/v1/conversation/conversation/not-a-uuid/name"),
            ("delete", "/api/v1/conversation/conversation/not-a-uuid"),
            ("post", "/api/v1/chatbot/chat/not-a-uuid"),
        ],
    )
    async def test_a_malformed_id_is_422_not_a_database_error(self, authenticated_client_with_agent, method, path):
        response = await authenticated_client_with_agent.request(method, path, data={"name": "x"})

        assert response.status_code == 422

    async def test_delete_other_users_conversation_returns_404(self, db_session, authenticated_client_with_agent):
        from app.modules.account.models import User

        other_user = User(clerk_id="clerk_other_del", email="other_del@example.com")
        db_session.add(other_user)
        await db_session.flush()
        await db_session.refresh(other_user)

        other_conv = Conversation(
            user_id=other_user.id,
            name="Other's Chat",
        )
        db_session.add(other_conv)
        await db_session.flush()

        response = await authenticated_client_with_agent.delete(f"/api/v1/conversation/conversation/{other_conv.id}")
        assert response.status_code == 404


@pytest.fixture
async def untitled_conversation(db_session, test_user):
    conv = Conversation(user_id=test_user.id, name="")
    db_session.add(conv)
    await db_session.flush()
    await db_session.refresh(conv)
    return conv


class TestGenerateConversationTitle:
    """Tests for POST /api/v1/conversation/conversation/{id}/title"""

    def _url(self, conversation_id):
        return f"/api/v1/conversation/conversation/{conversation_id}/title"

    async def test_unauthenticated_returns_401(self, client, untitled_conversation):
        response = await client.post(self._url(untitled_conversation.id))
        assert response.status_code == 401

    async def test_untitled_conversation_gets_a_title(
        self, authenticated_client_with_agent, untitled_conversation, mock_agent
    ):
        mock_agent.title_for = AsyncMock(return_value="Grocery budget")
        response = await authenticated_client_with_agent.post(self._url(untitled_conversation.id))
        assert response.status_code == 200
        assert response.json()["name"] == "Grocery budget"
        mock_agent.title_for.assert_awaited_once_with(untitled_conversation.id, untitled_conversation.user_id)

    async def test_named_conversation_is_unchanged(
        self, authenticated_client_with_agent, untitled_conversation, mock_agent, db_session
    ):
        untitled_conversation.name = "My name"
        await db_session.flush()
        mock_agent.title_for = AsyncMock(return_value="Other")
        response = await authenticated_client_with_agent.post(self._url(untitled_conversation.id))
        assert response.json()["name"] == "My name"
        mock_agent.title_for.assert_not_awaited()

    async def test_rename_during_the_model_call_wins(
        self, authenticated_client_with_agent, untitled_conversation, mock_agent, db_session
    ):
        # A rename lands while the model is still writing the title: the title
        # must not overwrite it, and the route answers with the user's name.
        # synchronize_session=False leaves the route's loaded row stale, as a
        # rename committed by another request would.
        async def rename_then_title(*_):
            await db_session.execute(
                update(Conversation)
                .where(Conversation.id == untitled_conversation.id)
                .values(name="User rename")
                .execution_options(synchronize_session=False)
            )
            return "Generated"

        mock_agent.title_for = AsyncMock(side_effect=rename_then_title)
        response = await authenticated_client_with_agent.post(self._url(untitled_conversation.id))
        assert response.status_code == 200
        assert response.json()["name"] == "User rename"

    async def test_no_title_leaves_the_conversation_unchanged(
        self, authenticated_client_with_agent, untitled_conversation, mock_agent
    ):
        # The agent answers None for no reply yet or a failed model call
        # (unit-tested on ChatbotAgent.title_for); the route still answers 200.
        mock_agent.title_for = AsyncMock(return_value=None)
        response = await authenticated_client_with_agent.post(self._url(untitled_conversation.id))
        assert response.status_code == 200
        assert response.json()["name"] == ""

    async def test_other_users_conversation_returns_404(self, db_session, authenticated_client_with_agent):
        from app.modules.account.models import User

        other = User(clerk_id="clerk_title_other", email="title_other@example.com")
        db_session.add(other)
        await db_session.flush()
        conv = Conversation(user_id=other.id, name="")
        db_session.add(conv)
        await db_session.flush()

        response = await authenticated_client_with_agent.post(self._url(conv.id))
        assert response.status_code == 404
