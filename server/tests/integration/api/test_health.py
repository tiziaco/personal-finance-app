"""Integration tests for system health endpoints — /, /health, /ready."""

import pytest

pytestmark = pytest.mark.integration


class TestRootEndpoint:
    """Tests for GET /"""

    async def test_returns_200(self, unauthenticated_client):
        response = await unauthenticated_client.get("/")
        assert response.status_code == 200

    async def test_response_schema(self, unauthenticated_client):
        response = await unauthenticated_client.get("/")
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "status" in data
        assert "environment" in data
        assert data["status"] == "healthy"

    async def test_swagger_url_in_response(self, unauthenticated_client):
        response = await unauthenticated_client.get("/")
        data = response.json()
        assert "swagger_url" in data


class TestHealthEndpoint:
    """Tests for GET /health"""

    async def test_returns_valid_status_code(self, unauthenticated_client):
        response = await unauthenticated_client.get("/health")
        assert response.status_code in [200, 503]

    async def test_response_has_status_and_timestamp(self, unauthenticated_client):
        response = await unauthenticated_client.get("/health")
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert data["status"] in ["healthy", "degraded"]

    async def test_degraded_without_agents(self, unauthenticated_client):
        """Health is degraded when agents aren't initialized (test environment)."""
        response = await unauthenticated_client.get("/health")
        data = response.json()
        # In tests, agents are never initialized → always degraded
        assert data["status"] == "degraded"
        assert response.status_code == 503


class TestReadyEndpoint:
    """Tests for GET /ready"""

    async def test_requires_auth_returns_401(self, client):
        response = await client.get("/ready")
        assert response.status_code == 401

    async def test_with_auth_returns_status(self, authenticated_client):
        response = await authenticated_client.get("/ready")
        # 200 or 503 — agents won't be ready but endpoint should respond
        assert response.status_code in [200, 503]

    async def test_with_auth_response_has_components(self, authenticated_client):
        response = await authenticated_client.get("/ready")
        data = response.json()
        assert "status" in data
        assert "components" in data
        assert "version" in data
        assert "environment" in data
