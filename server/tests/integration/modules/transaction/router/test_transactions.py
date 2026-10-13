"""Transaction routes against a real database."""

import uuid

import pytest
from uuid_utils.compat import uuid7

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


VALID = {"date": "2026-03-03", "merchant": "Späti", "amount": "-4.50", "category": "food_groceries"}


class TestCreate:
    async def test_creates_and_returns_201(self, authenticated_client):
        response = await authenticated_client.post(BASE, json=VALID | {"description": "  "})
        assert response.status_code == 201
        body = response.json()
        assert body["amount"] == "-4.50"  # a string on the wire
        assert body["confidence"] == 1.0
        assert body["description"] is None
        assert uuid.UUID(body["id"]).version == 7
        assert "fingerprint" not in body and "user_id" not in body

    async def test_accepts_a_json_number_amount(self, authenticated_client):
        response = await authenticated_client.post(BASE, json=VALID | {"amount": 12.5})
        assert response.status_code == 201
        assert response.json()["amount"] == "12.50"

    @pytest.mark.parametrize(
        "patch",
        [
            {"amount": "1.005"},
            {"amount": "1234567890123"},
            {"merchant": "   "},
            {"merchant": "x" * 256},
            {"description": "x" * 1001},
            {"category": "no_such_slug"},
            {"date": "2026-02-30"},
        ],
    )
    async def test_invalid_input_is_422(self, authenticated_client, patch):
        assert (await authenticated_client.post(BASE, json=VALID | patch)).status_code == 422

    async def test_a_duplicate_is_409_with_the_existing_id(self, authenticated_client, test_user, make_transaction):
        existing = await make_transaction(test_user)
        response = await authenticated_client.post(BASE, json=VALID)
        assert response.status_code == 409
        assert response.json()["error"] == "DUPLICATE_TRANSACTION"
        assert response.json()["details"] == {"existing_transaction_id": str(existing.id)}

    async def test_allow_duplicate_is_201(self, authenticated_client, test_user, make_transaction):
        await make_transaction(test_user)
        assert (await authenticated_client.post(BASE, json=VALID | {"allow_duplicate": True})).status_code == 201


class TestUpdate:
    async def test_partial_edit(self, authenticated_client, test_user, make_transaction):
        txn = await make_transaction(test_user, description="Old", confidence=0.4)
        response = await authenticated_client.patch(f"{BASE}/{txn.id}", json={"description": None})
        assert response.status_code == 200
        assert response.json()["description"] is None
        assert response.json()["merchant"] == "Späti"
        assert response.json()["confidence"] == 1.0

    async def test_null_on_a_required_field_is_422(self, authenticated_client, test_user, make_transaction):
        txn = await make_transaction(test_user)
        assert (await authenticated_client.patch(f"{BASE}/{txn.id}", json={"merchant": None})).status_code == 422

    async def test_another_users_transaction_is_404(self, authenticated_client, other_user, make_transaction):
        txn = await make_transaction(other_user)
        response = await authenticated_client.patch(f"{BASE}/{txn.id}", json={"merchant": "x"})
        assert response.status_code == 404
        assert response.json()["error"] == "TRANSACTION_NOT_FOUND"

    async def test_a_missing_id_is_404(self, authenticated_client):
        assert (await authenticated_client.patch(f"{BASE}/{uuid7()}", json={"merchant": "x"})).status_code == 404


class TestDelete:
    async def test_soft_deletes_and_answers_204(self, authenticated_client, test_user, make_transaction, db_session):
        txn = await make_transaction(test_user)
        assert (await authenticated_client.delete(f"{BASE}/{txn.id}")).status_code == 204
        await db_session.refresh(txn)
        assert txn.deleted_at is not None
        assert (await authenticated_client.delete(f"{BASE}/{txn.id}")).status_code == 404

    async def test_another_users_transaction_is_404(self, authenticated_client, other_user, make_transaction):
        txn = await make_transaction(other_user)
        assert (await authenticated_client.delete(f"{BASE}/{txn.id}")).status_code == 404
