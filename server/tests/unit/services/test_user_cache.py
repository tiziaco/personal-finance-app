"""Tests for app.services.user.cache.UserCache.

Expiry is driven by an injected fake clock, never by sleeping. Note TTLCache
uses a monotonic timer, NOT wall clock — patching datetime.now() would not
expire anything, which is why UserCache takes a `timer` argument.
"""

import inspect

import pytest

from app.services.user.cache import (
    _MISS,
    UserCache,
)

pytestmark = pytest.mark.unit

ROLE_TTL = 60.0
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
    return UserCache(ttl=TTL, role_ttl=ROLE_TTL, timer=clock)


class TestOrgRoleCache:
    async def test_set_then_get_returns_role(self, cache):
        await cache.set_org_role("clerk_1", "project_manager")
        assert await cache.get_org_role("clerk_1") == "project_manager"

    async def test_unknown_key_returns_miss(self, cache):
        assert await cache.get_org_role("clerk_unknown") is _MISS

    async def test_overwrite_wins(self, cache):
        await cache.set_org_role("clerk_1", "supplier")
        await cache.set_org_role("clerk_1", "project_manager")
        assert await cache.get_org_role("clerk_1") == "project_manager"

    async def test_alive_just_before_ttl(self, cache, clock):
        await cache.set_org_role("clerk_1", "supplier")
        clock.advance(ROLE_TTL - 1)
        assert await cache.get_org_role("clerk_1") == "supplier"

    async def test_expired_after_ttl(self, cache, clock):
        await cache.set_org_role("clerk_1", "supplier")
        clock.advance(ROLE_TTL + 1)
        assert await cache.get_org_role("clerk_1") is _MISS


class TestSupplierIdCache:
    async def test_set_then_get_returns_supplier_id(self, cache):
        await cache.set_supplier_id("user_1", "supplier_9")
        assert await cache.get_supplier_id("user_1") == "supplier_9"

    async def test_unknown_key_returns_miss(self, cache):
        assert await cache.get_supplier_id("user_unknown") is _MISS

    async def test_cached_none_is_a_value_not_a_miss(self, cache):
        """A cached None means "known not linked" and must short-circuit the DB."""
        await cache.set_supplier_id("user_1", None)

        cached = await cache.get_supplier_id("user_1")

        assert cached is None
        assert cached is not _MISS

    async def test_alive_just_before_ttl(self, cache, clock):
        await cache.set_supplier_id("user_1", "supplier_9")
        clock.advance(TTL - 1)
        assert await cache.get_supplier_id("user_1") == "supplier_9"

    async def test_expired_after_ttl(self, cache, clock):
        await cache.set_supplier_id("user_1", "supplier_9")
        clock.advance(TTL + 1)
        assert await cache.get_supplier_id("user_1") is _MISS


class TestTwoTtls:
    """The org role must expire well before the supplier link."""

    async def test_role_expires_first(self, cache, clock):
        await cache.set_org_role("clerk_1", "supplier")
        await cache.set_supplier_id("user_1", "supplier_9")

        clock.advance(ROLE_TTL + 1)

        assert await cache.get_org_role("clerk_1") is _MISS
        assert await cache.get_supplier_id("user_1") == "supplier_9"

    async def test_supplier_expires_eventually(self, cache, clock):
        await cache.set_supplier_id("user_1", "supplier_9")

        clock.advance(TTL + 1)

        assert await cache.get_supplier_id("user_1") is _MISS


class TestInvalidateUser:
    async def test_clerk_id_clears_only_the_role(self, cache):
        await cache.set_org_role("clerk_1", "supplier")
        await cache.set_supplier_id("user_1", "supplier_9")

        await cache.invalidate_user(clerk_id="clerk_1")

        assert await cache.get_org_role("clerk_1") is _MISS
        assert await cache.get_supplier_id("user_1") == "supplier_9"

    async def test_user_id_clears_only_the_supplier_link(self, cache):
        await cache.set_org_role("clerk_1", "supplier")
        await cache.set_supplier_id("user_1", "supplier_9")

        await cache.invalidate_user(user_id="user_1")

        assert await cache.get_org_role("clerk_1") == "supplier"
        assert await cache.get_supplier_id("user_1") is _MISS

    async def test_both_clears_both(self, cache):
        await cache.set_org_role("clerk_1", "supplier")
        await cache.set_supplier_id("user_1", "supplier_9")

        await cache.invalidate_user(clerk_id="clerk_1", user_id="user_1")

        assert await cache.get_org_role("clerk_1") is _MISS
        assert await cache.get_supplier_id("user_1") is _MISS

    async def test_unknown_ids_do_not_raise(self, cache):
        await cache.invalidate_user(clerk_id="nope", user_id="nope")

    async def test_no_arguments_is_a_noop(self, cache):
        """Must not raise: the GDPR flow calls this after its commit."""
        await cache.set_org_role("clerk_1", "supplier")
        await cache.set_supplier_id("user_1", "supplier_9")

        await cache.invalidate_user()

        assert await cache.get_org_role("clerk_1") == "supplier"
        assert await cache.get_supplier_id("user_1") == "supplier_9"


class TestClearAndReset:
    async def test_reset_empties_both(self, cache):
        await cache.set_org_role("clerk_1", "supplier")
        await cache.set_supplier_id("user_1", "supplier_9")

        cache.reset()

        assert await cache.get_org_role("clerk_1") is _MISS
        assert await cache.get_supplier_id("user_1") is _MISS

    async def test_clear_empties_both(self, cache):
        await cache.set_org_role("clerk_1", "supplier")
        await cache.set_supplier_id("user_1", "supplier_9")

        await cache.clear()

        assert await cache.get_org_role("clerk_1") is _MISS
        assert await cache.get_supplier_id("user_1") is _MISS

    def test_reset_is_not_a_coroutine_function(self):
        """conftest's sync autouse fixture calls reset() without awaiting."""
        assert not inspect.iscoroutinefunction(UserCache.reset)


class TestBounds:
    async def test_evicts_beyond_maxsize(self, clock):
        cache = UserCache(maxsize=2, ttl=TTL, role_ttl=ROLE_TTL, timer=clock)

        for i in range(3):
            await cache.set_supplier_id(f"user_{i}", f"supplier_{i}")

        assert len(cache._supplier_id) == 2

    async def test_role_cache_is_bounded_too(self, clock):
        cache = UserCache(maxsize=2, ttl=TTL, role_ttl=ROLE_TTL, timer=clock)

        for i in range(3):
            await cache.set_org_role(f"clerk_{i}", "supplier")

        assert len(cache._org_role) == 2


class TestAsyncSeam:
    """The public API stays async so a Redis backend can slot in unchanged."""

    @pytest.mark.parametrize(
        "name",
        [
            "get_org_role",
            "set_org_role",
            "get_supplier_id",
            "set_supplier_id",
            "invalidate_user",
            "clear",
        ],
    )
    def test_public_method_is_async(self, name):
        assert inspect.iscoroutinefunction(getattr(UserCache, name))
