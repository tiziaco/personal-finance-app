"""Tests for app.modules.supplier.cache.SupplierCache.

Expiry is driven by an injected fake clock, never by sleeping. Note TTLCache
uses a monotonic timer, NOT wall clock — patching datetime.now() would not
expire anything, which is why SupplierCache takes a `timer` argument.
"""

import inspect
import uuid

import pytest

from app.modules.supplier.cache import SupplierCache
from app.utils.cache import MISS

pytestmark = pytest.mark.unit

USER_1 = uuid.UUID("0199a8b0-0000-7000-8000-000000000001")
UNKNOWN_USER = uuid.UUID("0199a8b0-0000-7000-8000-0000000000ff")
SUPPLIER_9 = uuid.UUID("0199a8b0-0000-7000-8000-000000000009")

TTL = 300.0


class FakeClock:
    """Monotonic clock stand-in that only moves when a test moves it."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def cache(clock):
    return SupplierCache(ttl=TTL, timer=clock)


class TestSupplierIdCache:
    async def test_set_then_get_returns_supplier_id(self, cache):
        await cache.set_supplier_id(USER_1, SUPPLIER_9)
        assert await cache.get_supplier_id(USER_1) == SUPPLIER_9

    async def test_unknown_key_returns_miss(self, cache):
        assert await cache.get_supplier_id(UNKNOWN_USER) is MISS

    async def test_cached_none_is_a_value_not_a_miss(self, cache):
        """A cached None means "known not linked" and must short-circuit the DB."""
        await cache.set_supplier_id(USER_1, None)

        cached = await cache.get_supplier_id(USER_1)

        assert cached is None
        assert cached is not MISS

    async def test_alive_just_before_ttl(self, cache, clock):
        await cache.set_supplier_id(USER_1, SUPPLIER_9)
        clock.advance(TTL - 1)
        assert await cache.get_supplier_id(USER_1) == SUPPLIER_9

    async def test_expired_after_ttl(self, cache, clock):
        await cache.set_supplier_id(USER_1, SUPPLIER_9)
        clock.advance(TTL + 1)
        assert await cache.get_supplier_id(USER_1) is MISS


class TestInvalidateUser:
    async def test_user_id_clears_the_supplier_link(self, cache):
        await cache.set_supplier_id(USER_1, SUPPLIER_9)

        await cache.invalidate_user(user_id=USER_1)

        assert await cache.get_supplier_id(USER_1) is MISS

    async def test_unknown_id_does_not_raise(self, cache):
        await cache.invalidate_user(user_id=UNKNOWN_USER)


class TestClearAndReset:
    async def test_reset_empties_the_cache(self, cache):
        await cache.set_supplier_id(USER_1, SUPPLIER_9)

        cache.reset()

        assert await cache.get_supplier_id(USER_1) is MISS

    async def test_clear_empties_the_cache(self, cache):
        await cache.set_supplier_id(USER_1, SUPPLIER_9)

        await cache.clear()

        assert await cache.get_supplier_id(USER_1) is MISS

    def test_reset_is_not_a_coroutine_function(self):
        """conftest's sync autouse fixture calls reset() without awaiting."""
        assert not inspect.iscoroutinefunction(SupplierCache.reset)


class TestBounds:
    async def test_evicts_beyond_maxsize(self, clock):
        cache = SupplierCache(maxsize=2, ttl=TTL, timer=clock)

        for i in range(3):
            await cache.set_supplier_id(uuid.UUID(int=i), uuid.UUID(int=100 + i))

        assert len(cache._supplier_id) == 2


class TestAsyncSeam:
    """The public API stays async so a Redis backend can slot in unchanged."""

    @pytest.mark.parametrize(
        "name",
        [
            "get_supplier_id",
            "set_supplier_id",
            "invalidate_user",
            "clear",
        ],
    )
    def test_public_method_is_async(self, name):
        assert inspect.iscoroutinefunction(getattr(SupplierCache, name))
