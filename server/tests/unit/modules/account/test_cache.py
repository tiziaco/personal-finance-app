"""Tests for app.modules.account.cache.UserCache.

Expiry is driven by an injected fake clock, never by sleeping. Note TTLCache
uses a monotonic timer, NOT wall clock — patching datetime.now() would not
expire anything, which is why UserCache takes a `timer` argument.
"""

import inspect

import pytest

from app.modules.account.cache import UserCache
from app.utils.cache import MISS

pytestmark = pytest.mark.unit

ROLE_TTL = 60.0


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
    return UserCache(role_ttl=ROLE_TTL, timer=clock)


class TestOrgRoleCache:
    async def test_set_then_get_returns_role(self, cache):
        await cache.set_org_role("clerk_1", "project_manager")
        assert await cache.get_org_role("clerk_1") == "project_manager"

    async def test_unknown_key_returns_miss(self, cache):
        assert await cache.get_org_role("clerk_unknown") is MISS

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
        assert await cache.get_org_role("clerk_1") is MISS


class TestInvalidateUser:
    async def test_clerk_id_clears_the_role(self, cache):
        await cache.set_org_role("clerk_1", "supplier")

        await cache.invalidate_user(clerk_id="clerk_1")

        assert await cache.get_org_role("clerk_1") is MISS

    async def test_unknown_id_does_not_raise(self, cache):
        await cache.invalidate_user(clerk_id="nope")


class TestClearAndReset:
    async def test_reset_empties_the_cache(self, cache):
        await cache.set_org_role("clerk_1", "supplier")

        cache.reset()

        assert await cache.get_org_role("clerk_1") is MISS

    async def test_clear_empties_the_cache(self, cache):
        await cache.set_org_role("clerk_1", "supplier")

        await cache.clear()

        assert await cache.get_org_role("clerk_1") is MISS

    def test_reset_is_not_a_coroutine_function(self):
        """conftest's sync autouse fixture calls reset() without awaiting."""
        assert not inspect.iscoroutinefunction(UserCache.reset)


class TestBounds:
    async def test_role_cache_is_bounded(self, clock):
        cache = UserCache(maxsize=2, role_ttl=ROLE_TTL, timer=clock)

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
            "invalidate_user",
            "clear",
        ],
    )
    def test_public_method_is_async(self, name):
        assert inspect.iscoroutinefunction(getattr(UserCache, name))
