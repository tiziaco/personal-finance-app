"""Integration tests for GET /api/v1/auth/me — authentication and user profile."""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select

from app.modules.account.models import User

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

        assert data["id"] == str(test_user.id)
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


class TestGetMeWithoutOrganisation:
    """The user is the tenant: a token with no org claims is a full user."""

    @patch("app.modules.account.service.clerk_client.get_primary_email", return_value="no-org@example.com")
    @patch("app.modules.account.service.clerk_client.get_user")
    @patch("app.api.middlewares.auth.clerk_jwt_verifier")
    async def test_a_token_without_org_claims_provisions_the_user(
        self, mock_verifier, mock_get_user, _mock_email, client, db_session
    ):
        mock_verifier.verify_token.return_value = {"sub": "clerk_no_org_001"}
        clerk_user = MagicMock()
        clerk_user.first_name = "No"
        clerk_user.last_name = "Org"
        clerk_user.image_url = None
        clerk_user.primary_email_address_id = "email_1"
        clerk_user.updated_at = None
        clerk_user.public_metadata = {}
        mock_get_user.return_value = clerk_user

        response = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer t"})

        assert response.status_code == 200
        assert response.json()["email"] == "no-org@example.com"
        row = (await db_session.execute(select(User).where(User.clerk_id == "clerk_no_org_001"))).scalar_one()
        assert row.email == "no-org@example.com"
