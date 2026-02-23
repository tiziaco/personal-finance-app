"""Integration tests for GET /api/v1/insights."""

import pytest


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_get_insights_unauthenticated(client):
    response = await client.get("/api/v1/insights")
    assert response.status_code == 401
