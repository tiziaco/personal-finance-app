"""Integration tests for get_user_conversation dependency — ownership enforcement."""

import uuid

import pytest
from uuid_utils.compat import uuid7

from app.modules.account.models import User
from app.modules.conversation.models import Conversation

pytestmark = pytest.mark.integration


class TestConversationAccessDependency:
    """Tests for get_user_conversation dependency via API calls."""

    async def test_nonexistent_conversation_returns_404(self, authenticated_client):
        """Conversation not in DB → 404 from ConversationNotFoundError."""
        fake_id = uuid7()
        response = await authenticated_client.patch(
            f"/api/v1/conversation/conversation/{fake_id}/name",
            data={"name": "New Name"},
        )
        assert response.status_code == 404

    async def test_error_response_has_error_code(self, authenticated_client):
        """404 response body contains error code for client identification."""
        fake_id = uuid7()
        response = await authenticated_client.patch(
            f"/api/v1/conversation/conversation/{fake_id}/name",
            data={"name": "New Name"},
        )
        data = response.json()
        assert "error" in data
        assert data["error"] == "CONVERSATION_NOT_FOUND"

    async def test_other_users_conversation_returns_404(self, db_session, authenticated_client):
        """Conversation exists but belongs to a different user → 404, as if missing."""
        other_user = User(
            clerk_id="clerk_access_other",
            org_id="test_org_123",
            email="access_other@example.com",
        )
        db_session.add(other_user)
        await db_session.flush()
        await db_session.refresh(other_user)

        other_conv = Conversation(
            user_id=other_user.id,
            name="Not Mine",
        )
        db_session.add(other_conv)
        await db_session.flush()

        response = await authenticated_client.patch(
            f"/api/v1/conversation/conversation/{other_conv.id}/name",
            data={"name": "Hijack"},
        )
        assert response.status_code == 404

    async def test_other_users_conversation_is_indistinguishable_from_a_missing_one(
        self, db_session, authenticated_client
    ):
        """Same error code as a missing id, and no user id in the message."""
        other_user = User(
            clerk_id="clerk_access_other_2",
            org_id="test_org_123",
            email="access_other_2@example.com",
        )
        db_session.add(other_user)
        await db_session.flush()
        await db_session.refresh(other_user)

        other_conv = Conversation(user_id=other_user.id, name="Not Mine")
        db_session.add(other_conv)
        await db_session.flush()

        response = await authenticated_client.patch(
            f"/api/v1/conversation/conversation/{other_conv.id}/name",
            data={"name": "Hijack"},
        )
        data = response.json()
        assert response.status_code == 404
        assert data["error"] == "CONVERSATION_NOT_FOUND"
        assert str(other_user.id) not in response.text
