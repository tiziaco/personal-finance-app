"""Integration tests for /api/v1/transactions endpoints.

Uses a real test database and mocked auth (clerk_id injected via dependency override).
"""

from datetime import datetime, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlmodel import select

from app.api.dependencies.auth import get_current_user
from app.models.transaction import CategoryEnum, Transaction
from app.models.user import User

pytestmark = pytest.mark.integration

MOCK_CLERK_ID = "clerk_test_user_001"
BASE_URL = "/api/v1/transactions"


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def test_user(db_session):
    """Create a test user in the DB."""
    user = User(
        clerk_id=MOCK_CLERK_ID,
        email="test@example.com",
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.fixture
def auth_client(client, test_user):
    """Client with auth dependency overridden to return test_user."""
    from app.main import app
    app.dependency_overrides[get_current_user] = lambda: test_user
    yield client
    app.dependency_overrides.pop(get_current_user, None)


@pytest_asyncio.fixture
async def transaction(db_session, test_user):
    """A single transaction belonging to test_user."""
    tx = Transaction(
        user_id=test_user.id,
        date=datetime(2024, 3, 15, tzinfo=timezone.utc),
        merchant="Supermarket ABC",
        amount=42.50,
        category=CategoryEnum.FOOD_GROCERIES,
        confidence_score=1.0,
    )
    db_session.add(tx)
    await db_session.flush()
    await db_session.refresh(tx)
    return tx


@pytest_asyncio.fixture
async def other_user_transaction(db_session):
    """A transaction belonging to a different user."""
    other_user = User(clerk_id="clerk_other", email="other@example.com")
    db_session.add(other_user)
    await db_session.flush()
    await db_session.refresh(other_user)

    tx = Transaction(
        user_id=other_user.id,
        date=datetime(2024, 3, 15, tzinfo=timezone.utc),
        merchant="Other Bank",
        amount=100.0,
        category=CategoryEnum.MISCELLANEOUS,
        confidence_score=1.0,
    )
    db_session.add(tx)
    await db_session.flush()
    await db_session.refresh(tx)
    return tx


# ── Auth tests ────────────────────────────────────────────────────────────────

class TestAuth:
    @pytest.mark.asyncio
    async def test_unauthenticated_get_returns_401(self, client):
        response = await client.get(BASE_URL)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_unauthenticated_post_returns_401(self, client):
        response = await client.post(BASE_URL, json={})
        assert response.status_code == 401


# ── Create ────────────────────────────────────────────────────────────────────

class TestCreate:
    @pytest.mark.asyncio
    async def test_creates_transaction(self, auth_client, db_session, test_user):
        payload = {
            "date": "2024-03-15T10:00:00",
            "merchant": "Coffee Shop",
            "amount": 4.50,
            "category": "Bars & Restaurants",
        }
        response = await auth_client.post(BASE_URL, json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["merchant"] == "Coffee Shop"
        assert data["confidence_score"] == 1.0
        assert data["user_id"] == test_user.id

    @pytest.mark.asyncio
    async def test_validation_error_on_missing_required_field(self, auth_client):
        payload = {"merchant": "Shop", "amount": 10.0}  # missing date and category
        response = await auth_client.post(BASE_URL, json=payload)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_validation_error_on_invalid_confidence_score(self, auth_client):
        payload = {
            "date": "2024-03-15T10:00:00",
            "merchant": "Shop",
            "amount": 10.0,
            "category": "Shopping",
            "confidence_score": 1.5,  # > 1.0
        }
        response = await auth_client.post(BASE_URL, json=payload)
        assert response.status_code == 422


# ── List ──────────────────────────────────────────────────────────────────────

class TestList:
    @pytest.mark.asyncio
    async def test_returns_only_own_transactions(
        self, auth_client, transaction, other_user_transaction
    ):
        response = await auth_client.get(BASE_URL)

        assert response.status_code == 200
        data = response.json()
        ids = [item["id"] for item in data["items"]]
        assert transaction.id in ids
        assert other_user_transaction.id not in ids

    @pytest.mark.asyncio
    async def test_excludes_soft_deleted_transactions(
        self, auth_client, db_session, test_user, transaction
    ):
        transaction.soft_delete()
        db_session.add(transaction)
        await db_session.flush()

        response = await auth_client.get(BASE_URL)

        ids = [item["id"] for item in response.json()["items"]]
        assert transaction.id not in ids

    @pytest.mark.asyncio
    async def test_pagination_offset_and_limit(self, auth_client, db_session, test_user):
        # Create 5 transactions
        for i in range(5):
            db_session.add(Transaction(
                user_id=test_user.id,
                date=datetime(2024, 1, i + 1, tzinfo=timezone.utc),
                merchant=f"Merchant {i}",
                amount=float(i),
                category=CategoryEnum.MISCELLANEOUS,
                confidence_score=1.0,
            ))
        await db_session.flush()

        response = await auth_client.get(f"{BASE_URL}?offset=0&limit=2")
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] >= 5
        assert data["offset"] == 0
        assert data["limit"] == 2

    @pytest.mark.asyncio
    async def test_filter_by_category(self, auth_client, db_session, test_user):
        db_session.add(Transaction(
            user_id=test_user.id,
            date=datetime(2024, 3, 1, tzinfo=timezone.utc),
            merchant="Gym",
            amount=30.0,
            category=CategoryEnum.LEISURE_ENTERTAINMENT,
            confidence_score=1.0,
        ))
        await db_session.flush()

        response = await auth_client.get(
            BASE_URL,
            params={"category": CategoryEnum.LEISURE_ENTERTAINMENT.value},
        )
        data = response.json()
        assert all(item["category"] == CategoryEnum.LEISURE_ENTERTAINMENT for item in data["items"])

    @pytest.mark.asyncio
    async def test_filter_by_merchant_substring(self, auth_client, transaction):
        response = await auth_client.get(f"{BASE_URL}?merchant=supermarket")
        data = response.json()
        assert any(item["id"] == transaction.id for item in data["items"])


# ── Get single ────────────────────────────────────────────────────────────────

class TestGetSingle:
    @pytest.mark.asyncio
    async def test_returns_own_transaction(self, auth_client, transaction):
        response = await auth_client.get(f"{BASE_URL}/{transaction.id}")
        assert response.status_code == 200
        assert response.json()["id"] == transaction.id

    @pytest.mark.asyncio
    async def test_returns_404_for_other_users_transaction(
        self, auth_client, other_user_transaction
    ):
        response = await auth_client.get(f"{BASE_URL}/{other_user_transaction.id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent_id(self, auth_client):
        response = await auth_client.get(f"{BASE_URL}/999999")
        assert response.status_code == 404


# ── Update ────────────────────────────────────────────────────────────────────

class TestUpdate:
    @pytest.mark.asyncio
    async def test_partial_update(self, auth_client, transaction):
        original_amount = transaction.amount
        response = await auth_client.patch(
            f"{BASE_URL}/{transaction.id}",
            json={"merchant": "Updated Merchant"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["merchant"] == "Updated Merchant"
        assert data["amount"] == original_amount  # unchanged

    @pytest.mark.asyncio
    async def test_updated_at_is_refreshed(self, auth_client, db_session, transaction):
        original_updated_at = transaction.updated_at
        response = await auth_client.patch(
            f"{BASE_URL}/{transaction.id}",
            json={"merchant": "Changed"},
        )
        assert response.status_code == 200
        # Re-fetch to verify DB state
        await db_session.refresh(transaction)
        assert transaction.updated_at >= original_updated_at

    @pytest.mark.asyncio
    async def test_returns_404_for_other_users_transaction(
        self, auth_client, other_user_transaction
    ):
        response = await auth_client.patch(
            f"{BASE_URL}/{other_user_transaction.id}",
            json={"merchant": "Hack"},
        )
        assert response.status_code == 404


# ── Delete ────────────────────────────────────────────────────────────────────

class TestDelete:
    @pytest.mark.asyncio
    async def test_soft_deletes_transaction(self, auth_client, db_session, transaction):
        response = await auth_client.delete(f"{BASE_URL}/{transaction.id}")
        assert response.status_code == 204

        await db_session.refresh(transaction)
        assert transaction.deleted_at is not None

    @pytest.mark.asyncio
    async def test_deleted_transaction_excluded_from_list(
        self, auth_client, transaction
    ):
        await auth_client.delete(f"{BASE_URL}/{transaction.id}")
        list_response = await auth_client.get(BASE_URL)
        ids = [item["id"] for item in list_response.json()["items"]]
        assert transaction.id not in ids

    @pytest.mark.asyncio
    async def test_returns_404_for_other_users_transaction(
        self, auth_client, other_user_transaction
    ):
        response = await auth_client.delete(f"{BASE_URL}/{other_user_transaction.id}")
        assert response.status_code == 404


# ── Batch Update ──────────────────────────────────────────────────────────────

class TestBatchUpdate:
    @pytest.mark.asyncio
    async def test_updates_multiple_transactions(
        self, auth_client, db_session, test_user, transaction
    ):
        tx2 = Transaction(
            user_id=test_user.id,
            date=datetime(2024, 3, 16, tzinfo=timezone.utc),
            merchant="Old Name",
            amount=20.0,
            category=CategoryEnum.SHOPPING,
            confidence_score=1.0,
        )
        db_session.add(tx2)
        await db_session.flush()
        await db_session.refresh(tx2)

        response = await auth_client.patch(
            f"{BASE_URL}/batch",
            json={"items": [
                {"id": transaction.id, "merchant": "New A"},
                {"id": tx2.id, "merchant": "New B"},
            ]},
        )
        assert response.status_code == 200
        assert response.json()["updated"] == 2

    @pytest.mark.asyncio
    async def test_rolls_back_on_invalid_id(
        self, auth_client, db_session, transaction
    ):
        original_merchant = transaction.merchant
        response = await auth_client.patch(
            f"{BASE_URL}/batch",
            json={"items": [
                {"id": transaction.id, "merchant": "Changed"},
                {"id": 999999, "merchant": "Bad"},
            ]},
        )
        assert response.status_code == 404
        await db_session.refresh(transaction)
        assert transaction.merchant == original_merchant  # rolled back

    @pytest.mark.asyncio
    async def test_validation_error_on_oversized_batch(self, auth_client):
        items = [{"id": i, "merchant": "x"} for i in range(101)]
        response = await auth_client.patch(
            f"{BASE_URL}/batch", json={"items": items}
        )
        assert response.status_code == 422


# ── Batch Delete ──────────────────────────────────────────────────────────────

class TestBatchDelete:
    @pytest.mark.asyncio
    async def test_soft_deletes_multiple_transactions(
        self, auth_client, db_session, test_user, transaction
    ):
        tx2 = Transaction(
            user_id=test_user.id,
            date=datetime(2024, 3, 17, tzinfo=timezone.utc),
            merchant="Another",
            amount=15.0,
            category=CategoryEnum.SHOPPING,
            confidence_score=1.0,
        )
        db_session.add(tx2)
        await db_session.flush()
        await db_session.refresh(tx2)

        response = await auth_client.request(
            "DELETE",
            f"{BASE_URL}/batch",
            json={"ids": [transaction.id, tx2.id]},
        )
        assert response.status_code == 200
        assert response.json()["deleted"] == 2

        await db_session.refresh(transaction)
        await db_session.refresh(tx2)
        assert transaction.deleted_at is not None
        assert tx2.deleted_at is not None

    @pytest.mark.asyncio
    async def test_rolls_back_on_invalid_id(
        self, auth_client, db_session, transaction
    ):
        response = await auth_client.request(
            "DELETE",
            f"{BASE_URL}/batch",
            json={"ids": [transaction.id, 999999]},
        )
        assert response.status_code == 404
        await db_session.refresh(transaction)
        assert transaction.deleted_at is None  # rolled back

    @pytest.mark.asyncio
    async def test_returns_404_for_other_users_transactions(
        self, auth_client, other_user_transaction
    ):
        response = await auth_client.request(
            "DELETE",
            f"{BASE_URL}/batch",
            json={"ids": [other_user_transaction.id]},
        )
        assert response.status_code == 404
