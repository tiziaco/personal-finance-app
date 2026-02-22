"""Integration tests for GET/DELETE /api/v1/auth/me — authentication and user profile."""

import pytest
from unittest.mock import AsyncMock, patch

pytestmark = pytest.mark.integration


class TestGetMe:
    """Tests for GET /api/v1/auth/me"""

    async def test_unauthenticated_returns_401(self, client):
        """No auth header → middleware sets clerk_id=None → get_clerk_id raises 401."""
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401

    async def test_authenticated_returns_200(self, authenticated_client):
        response = await authenticated_client.get("/api/v1/auth/me")
        assert response.status_code == 200

    async def test_response_contains_user_fields(self, authenticated_client, test_user):
        response = await authenticated_client.get("/api/v1/auth/me")
        data = response.json()

        assert data["id"] == test_user.id
        assert data["clerk_id"] == test_user.clerk_id
        assert data["email"] == test_user.email

    async def test_response_schema_has_required_fields(self, authenticated_client):
        response = await authenticated_client.get("/api/v1/auth/me")
        data = response.json()

        for field in ["id", "clerk_id", "email", "created_at"]:
            assert field in data, f"Missing field: {field}"

    async def test_optional_fields_present_or_null(self, authenticated_client):
        response = await authenticated_client.get("/api/v1/auth/me")
        data = response.json()
        # These keys should be present (may be None)
        assert "first_name" in data
        assert "last_name" in data
        assert "avatar_url" in data


class TestDeleteMe:
    """Tests for DELETE /api/v1/auth/me"""

    async def test_unauthenticated_returns_401(self, client):
        response = await client.delete("/api/v1/auth/me")
        assert response.status_code == 401

    async def test_returns_204_on_success(
        self, authenticated_client_with_agent, test_user
    ):
        with patch("app.api.v1.auth.clerk_service.delete_user"), \
             patch("app.api.v1.auth.delete_user_memory", new_callable=AsyncMock), \
             patch("app.api.v1.auth.user_provider.invalidate_cache"):
            response = await authenticated_client_with_agent.delete("/api/v1/auth/me")

        assert response.status_code == 204

    async def test_anonymizes_user_record(
        self, db_session, authenticated_client_with_agent, test_user
    ):
        original_email = test_user.email
        original_clerk_id = test_user.clerk_id

        with patch("app.api.v1.auth.clerk_service.delete_user"), \
             patch("app.api.v1.auth.delete_user_memory", new_callable=AsyncMock), \
             patch("app.api.v1.auth.user_provider.invalidate_cache"):
            await authenticated_client_with_agent.delete("/api/v1/auth/me")

        await db_session.refresh(test_user)
        assert test_user.email != original_email
        assert test_user.clerk_id != original_clerk_id
        assert test_user.anonymized_at is not None
        assert test_user.first_name is None
        assert test_user.last_name is None

    async def test_calls_clerk_delete(
        self, authenticated_client_with_agent, test_user
    ):
        original_clerk_id = test_user.clerk_id
        with patch("app.api.v1.auth.clerk_service.delete_user") as mock_clerk, \
             patch("app.api.v1.auth.delete_user_memory", new_callable=AsyncMock), \
             patch("app.api.v1.auth.user_provider.invalidate_cache"):
            await authenticated_client_with_agent.delete("/api/v1/auth/me")

        mock_clerk.assert_called_once_with(original_clerk_id)

    async def test_clears_agent_history_for_each_conversation(
        self, db_session, authenticated_client_with_agent, test_user, mock_agent
    ):
        import uuid
        from app.models.conversation import Conversation

        conv_id = str(uuid.uuid4())
        conv = Conversation(id=conv_id, user_id=test_user.id, name="Test conv")
        db_session.add(conv)
        await db_session.flush()

        with patch("app.api.v1.auth.clerk_service.delete_user"), \
             patch("app.api.v1.auth.delete_user_memory", new_callable=AsyncMock), \
             patch("app.api.v1.auth.user_provider.invalidate_cache"):
            await authenticated_client_with_agent.delete("/api/v1/auth/me")

        mock_agent.clear_chat_history.assert_called_once_with(conv_id)
