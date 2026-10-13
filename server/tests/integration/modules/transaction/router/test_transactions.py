"""Transaction routes against a real database."""

import pytest

from app.modules.transaction import CATEGORIES

pytestmark = pytest.mark.integration

BASE = "/api/v1/transactions"


class TestListCategories:
    async def test_unauthenticated_returns_401(self, client):
        assert (await client.get(f"{BASE}/categories")).status_code == 401

    async def test_lists_every_category_in_display_order(self, authenticated_client):
        response = await authenticated_client.get(f"{BASE}/categories")
        assert response.status_code == 200
        assert response.json() == [{"value": slug, "label": label} for slug, label in CATEGORIES]
