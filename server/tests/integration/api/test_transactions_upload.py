"""Integration tests for CSV upload endpoints.

POST /api/v1/transactions/upload        — step 1: propose column mapping
POST /api/v1/transactions/upload/{id}/confirm — step 2: import
"""

import io
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from app.api.dependencies.auth import get_current_user
from app.main import app
from app.models.user import User

pytestmark = pytest.mark.integration

BASE_URL = "/api/v1/transactions/upload"

CSV_VALID = b"Buchungsdatum,Empfaenger,Betrag,Verwendungszweck\n2026-01-15,Netflix,12.99,Subscription\n"
CSV_WRONG_TYPE = b"not a csv"

MOCK_MAPPING = {
    "Buchungsdatum": "date",
    "Empfaenger": "merchant",
    "Betrag": "amount",
    "Verwendungszweck": "description",
}


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def test_user(db_session):
    user = User(clerk_id="user_test_csv_upload", email="csv@example.com")
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest.fixture
def auth_client(client, test_user):
    app.dependency_overrides[get_current_user] = lambda: test_user
    yield client
    app.dependency_overrides.pop(get_current_user, None)


# ── Upload endpoint (step 1) ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upload_valid_csv_returns_proposal(auth_client):
    with patch(
        "app.api.v1.transactions.CSVMappingService.get_profile",
        new_callable=AsyncMock,
        return_value=None,
    ), patch(
        "app.api.v1.transactions._propose_column_mapping",
        new_callable=AsyncMock,
        return_value=MOCK_MAPPING,
    ):
        response = await auth_client.post(
            BASE_URL,
            files={"file": ("transactions.csv", io.BytesIO(CSV_VALID), "text/csv")},
        )

    assert response.status_code == 200
    body = response.json()
    assert "mapping_id" in body
    assert body["proposed_mapping"] == MOCK_MAPPING
    assert len(body["sample_rows"]) <= 3
    assert "available_fields" in body
    assert "date" in body["available_fields"]
    assert "ignore" in body["available_fields"]
    assert "column_null_rates" in body
    assert set(body["column_null_rates"].keys()) == set(body["proposed_mapping"].keys())


@pytest.mark.asyncio
async def test_upload_returns_null_rates_for_sparse_column(auth_client):
    """Columns with all-null values in the file get null_rate=1.0."""
    csv_with_nulls = (
        b"Date,Merchant,Amount,Reference\n"
        b"2026-01-01,Netflix,12.99,\n"
        b"2026-01-02,Spotify,9.99,\n"
    )
    with patch(
        "app.api.v1.transactions.CSVMappingService.get_profile",
        new_callable=AsyncMock,
        return_value=None,
    ), patch(
        "app.api.v1.transactions._propose_column_mapping",
        new_callable=AsyncMock,
        return_value={"Date": "date", "Merchant": "merchant", "Amount": "amount", "Reference": "ignore"},
    ):
        response = await auth_client.post(
            BASE_URL,
            files={"file": ("test.csv", io.BytesIO(csv_with_nulls), "text/csv")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["column_null_rates"]["Reference"] == 1.0
    assert body["column_null_rates"]["Amount"] == 0.0


@pytest.mark.asyncio
async def test_upload_wrong_file_type_returns_422(auth_client):
    response = await auth_client.post(
        BASE_URL,
        files={"file": ("data.xlsx", io.BytesIO(CSV_WRONG_TYPE), "application/octet-stream")},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_upload_exceeds_row_cap_returns_422(auth_client, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "CSV_MAX_ROWS", 1)

    big_csv = b"Date,Merchant,Amount\n" + b"2026-01-01,Shop,10.00\n" * 2  # 2 rows, cap is 1

    with patch(
        "app.api.v1.transactions.CSVMappingService.get_profile",
        new_callable=AsyncMock,
        return_value=None,
    ):
        response = await auth_client.post(
            BASE_URL,
            files={"file": ("big.csv", io.BytesIO(big_csv), "text/csv")},
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_upload_uses_cached_mapping_when_available(auth_client):
    from app.models.csv_mapping_profile import CSVMappingProfile

    cached_profile = CSVMappingProfile(
        user_id="user_test_csv_upload",
        column_hash="somehash",
        mapping=MOCK_MAPPING,
        last_used_at=datetime.now(UTC),
    )

    with patch(
        "app.api.v1.transactions.CSVMappingService.get_profile",
        new_callable=AsyncMock,
        return_value=cached_profile,
    ), patch(
        "app.api.v1.transactions._propose_column_mapping",
        new_callable=AsyncMock,
    ) as mock_openai:
        response = await auth_client.post(
            BASE_URL,
            files={"file": ("transactions.csv", io.BytesIO(CSV_VALID), "text/csv")},
        )

    assert response.status_code == 200
    mock_openai.assert_not_called()  # cached mapping used — no OpenAI call


@pytest.mark.asyncio
async def test_upload_unauthenticated_returns_401(client):
    # client has DB session but no auth override → auth dependency raises 401
    response = await client.post(
        BASE_URL,
        files={"file": ("transactions.csv", io.BytesIO(CSV_VALID), "text/csv")},
    )
    assert response.status_code == 401


# ── Confirm endpoint (step 2) ──────────────────────────────────────────────────

CSV_TWO_ROWS = (
    b"Buchungsdatum,Empfaenger,Betrag,Verwendungszweck\n"
    b"2026-01-15,Netflix,12.99,Subscription\n"
    b"2026-01-16,Spotify,9.99,Music\n"
)


def make_session(csv_content: bytes, mapping: dict, user_id: str):
    from app.models.csv_upload_session import CSVUploadSession

    return CSVUploadSession(
        user_id=user_id,
        mapping_id="test-mapping-uuid",
        proposed_mapping=mapping,
        csv_content=csv_content.decode(),
        expires_at=datetime.now(UTC) + timedelta(minutes=30),
    )


@pytest_asyncio.fixture
def labeled_rows(test_user):
    from app.schemas.transaction import TransactionCreate
    from app.models.transaction import CategoryEnum

    return [
        TransactionCreate(
            date=datetime(2026, 1, 15, tzinfo=UTC),
            merchant="Netflix",
            amount=Decimal("12.99"),
            category=CategoryEnum.MEDIA_ELECTRONICS,
            confidence_score=0.95,
        ),
        TransactionCreate(
            date=datetime(2026, 1, 16, tzinfo=UTC),
            merchant="Spotify",
            amount=Decimal("9.99"),
            category=CategoryEnum.MEDIA_ELECTRONICS,
            confidence_score=0.95,
        ),
    ]


@pytest.mark.asyncio
async def test_confirm_valid_csv_imports_rows(auth_client, test_user, labeled_rows):
    session = make_session(CSV_TWO_ROWS, MOCK_MAPPING, test_user.id)

    with patch(
        "app.api.v1.transactions.CSVMappingService.get_session",
        new_callable=AsyncMock,
        return_value=session,
    ), patch(
        "app.api.v1.transactions.run_labeler",
        new_callable=AsyncMock,
        return_value=labeled_rows,
    ), patch(
        "app.api.v1.transactions.CSVMappingService.save_profile",
        new_callable=AsyncMock,
    ), patch(
        "app.api.v1.transactions.CSVMappingService.expire_session",
        new_callable=AsyncMock,
    ):
        response = await auth_client.post(
            f"{BASE_URL}/test-mapping-uuid/confirm",
            json={"confirmed_mapping": MOCK_MAPPING},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["imported"] == 2
    assert body["skipped"] == 0
    assert body["errors"] == []


@pytest.mark.asyncio
async def test_confirm_expired_session_returns_404(auth_client, test_user):
    with patch(
        "app.api.v1.transactions.CSVMappingService.get_session",
        new_callable=AsyncMock,
        return_value=None,
    ):
        response = await auth_client.post(
            f"{BASE_URL}/nonexistent-uuid/confirm",
            json={"confirmed_mapping": MOCK_MAPPING},
        )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_confirm_bad_rows_collected_in_errors(auth_client, test_user):
    csv_with_bad_row = (
        b"Date,Merchant,Amount\n"
        b"2026-01-15,Netflix,12.99\n"
        b"not-a-date,Spotify,bad-amount\n"
    )
    mapping = {"Date": "date", "Merchant": "merchant", "Amount": "amount"}
    session = make_session(csv_with_bad_row, mapping, test_user.id)

    with patch(
        "app.api.v1.transactions.CSVMappingService.get_session",
        new_callable=AsyncMock,
        return_value=session,
    ), patch(
        "app.api.v1.transactions.run_labeler",
        new_callable=AsyncMock,
        return_value=[],
    ), patch(
        "app.api.v1.transactions.CSVMappingService.save_profile",
        new_callable=AsyncMock,
    ), patch(
        "app.api.v1.transactions.CSVMappingService.expire_session",
        new_callable=AsyncMock,
    ):
        response = await auth_client.post(
            f"{BASE_URL}/test-mapping-uuid/confirm",
            json={"confirmed_mapping": mapping},
        )

    assert response.status_code == 200
    body = response.json()
    assert len(body["errors"]) >= 1


@pytest.mark.asyncio
async def test_confirm_second_upload_skips_duplicates(auth_client, test_user, db_session, labeled_rows):
    """Uploading the same file twice → second upload: imported=0, skipped=2."""
    from app.services.transaction.service import TransactionService

    for row in labeled_rows:
        await TransactionService.create(db_session, test_user.id, row)
    await db_session.flush()

    session = make_session(CSV_TWO_ROWS, MOCK_MAPPING, test_user.id)

    with patch(
        "app.api.v1.transactions.CSVMappingService.get_session",
        new_callable=AsyncMock,
        return_value=session,
    ), patch(
        "app.api.v1.transactions.run_labeler",
        new_callable=AsyncMock,
        return_value=labeled_rows,
    ), patch(
        "app.api.v1.transactions.CSVMappingService.save_profile",
        new_callable=AsyncMock,
    ), patch(
        "app.api.v1.transactions.CSVMappingService.expire_session",
        new_callable=AsyncMock,
    ):
        response = await auth_client.post(
            f"{BASE_URL}/test-mapping-uuid/confirm",
            json={"confirmed_mapping": MOCK_MAPPING},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["imported"] == 0
    assert body["skipped"] == 2
