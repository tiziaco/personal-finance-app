import hashlib
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.csv_mapping.service import CSVMappingService


def make_db_with_result(scalar_result):
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = scalar_result
    db.execute = AsyncMock(return_value=mock_result)
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock(side_effect=lambda obj: obj)
    return db


def column_hash(columns: list[str]) -> str:
    return hashlib.sha256("|".join(sorted(columns)).encode()).hexdigest()


@pytest.mark.asyncio
async def test_get_profile_returns_none_when_not_found():
    db = make_db_with_result(None)
    result = await CSVMappingService.get_profile(db, "user_abc", "somehash")
    assert result is None


@pytest.mark.asyncio
async def test_get_profile_returns_profile_when_found():
    from app.models.csv_mapping_profile import CSVMappingProfile

    fake = CSVMappingProfile(
        user_id="user_abc",
        column_hash="somehash",
        mapping={"Date": "date"},
        last_used_at=datetime.now(UTC),
    )
    db = make_db_with_result(fake)
    result = await CSVMappingService.get_profile(db, "user_abc", "somehash")
    assert result is fake


@pytest.mark.asyncio
async def test_save_profile_creates_new_when_not_found():
    db = make_db_with_result(None)
    await CSVMappingService.save_profile(
        db, "user_abc", "somehash", {"Date": "date"}
    )
    assert db.add.called


@pytest.mark.asyncio
async def test_compute_column_hash_is_order_independent():
    h1 = CSVMappingService.compute_column_hash(["Date", "Amount", "Merchant"])
    h2 = CSVMappingService.compute_column_hash(["Merchant", "Date", "Amount"])
    assert h1 == h2


@pytest.mark.asyncio
async def test_get_session_returns_none_for_expired():
    from app.models.csv_upload_session import CSVUploadSession

    expired = CSVUploadSession(
        user_id="user_abc",
        mapping_id="some-uuid",
        proposed_mapping={},
        csv_content="",
        expires_at=datetime.now(UTC) - timedelta(minutes=1),  # already expired
    )
    db = make_db_with_result(expired)
    result = await CSVMappingService.get_session(db, "some-uuid", "user_abc")
    assert result is None
