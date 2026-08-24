"""Tests for app.services.user.provider — in-memory cache behavior (no DB)."""

from datetime import UTC, datetime, timedelta

import pytest

from app.services.user.provider import CACHE_TTL, UserProvider, _clerk_id_cache

pytestmark = pytest.mark.unit


@pytest.fixture
def provider():
    return UserProvider()


class TestCacheGet:
    """Tests for _get_from_cache()."""

    def test_cache_hit_within_ttl(self, provider):
        _clerk_id_cache["clerk_1"] = ("user_uuid_1", datetime.now(UTC))

        result = provider._get_from_cache("clerk_1")
        assert result == "user_uuid_1"

    def test_cache_miss_empty(self, provider):
        result = provider._get_from_cache("clerk_nonexistent")
        assert result is None

    def test_cache_expired_returns_none(self, provider):
        expired_time = datetime.now(UTC) - CACHE_TTL - timedelta(seconds=1)
        _clerk_id_cache["clerk_old"] = ("user_uuid_old", expired_time)

        result = provider._get_from_cache("clerk_old")
        assert result is None
        # Expired entry should be removed
        assert "clerk_old" not in _clerk_id_cache


class TestCacheSet:
    """Tests for _set_cache()."""

    def test_set_cache_stores_entry(self, provider):
        provider._set_cache("clerk_new", "user_uuid_new")

        assert "clerk_new" in _clerk_id_cache
        user_id, cached_at = _clerk_id_cache["clerk_new"]
        assert user_id == "user_uuid_new"
        assert isinstance(cached_at, datetime)

    def test_set_cache_overwrites_existing(self, provider):
        provider._set_cache("clerk_x", "old_uuid")
        provider._set_cache("clerk_x", "new_uuid")

        user_id, _ = _clerk_id_cache["clerk_x"]
        assert user_id == "new_uuid"


class TestCacheInvalidate:
    """Tests for invalidate_cache() and clear_cache()."""

    def test_invalidate_removes_entry(self, provider):
        _clerk_id_cache["clerk_del"] = ("uuid", datetime.now(UTC))

        UserProvider.invalidate_cache("clerk_del")
        assert "clerk_del" not in _clerk_id_cache

    def test_invalidate_nonexistent_no_error(self, provider):
        UserProvider.invalidate_cache("clerk_nonexistent")  # no error

    def test_clear_cache_empties_all(self, provider):
        _clerk_id_cache["a"] = ("1", datetime.now(UTC))
        _clerk_id_cache["b"] = ("2", datetime.now(UTC))

        UserProvider.clear_cache()
        assert len(_clerk_id_cache) == 0
