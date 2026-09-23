"""In-memory cache for the user service.

``org_role`` — ``clerk_id -> role``. Feeds ``get_current_role()`` and so
``require_role()``: a stale entry keeps a revoked permission alive, hence the
short TTL.

Every public method is ``async def`` though nothing awaits: this module is the
seam for a future Redis backend, and swapping it must not touch a call site.

Import rule: stdlib, ``cachetools`` and ``app.core.logging`` only. Both
``repository`` and ``service`` import this module directly, so importing
either of them back here would break the import graph.

``TTLCache`` is not thread-safe and even reads mutate its expiry bookkeeping.
Every access here is on the event loop thread; if that changes, guard the
cache with a ``threading.RLock``. The cache is per-process, so a TTL bounds
staleness per worker, not globally.
"""

import time
from typing import (
    Callable,
    Final,
    Union,
)

from cachetools import TTLCache

from app.core.logging import logger
from app.utils.cache import MISS, Miss

DEFAULT_MAXSIZE: Final[int] = 10_000
DEFAULT_ROLE_TTL: Final[float] = 60.0  # org roles — feed authorization


class UserCache:
    """Bounded, TTL-expiring cache of org roles for auth data."""

    def __init__(
        self,
        *,
        maxsize: int = DEFAULT_MAXSIZE,
        role_ttl: float = DEFAULT_ROLE_TTL,
        timer: Callable[[], float] = time.monotonic,
    ) -> None:
        """Build the cache. ``maxsize`` bounds it; LRU eviction beyond it.

        ``role_ttl`` is short because a stale role keeps a revoked permission
        alive. ``timer`` is a monotonic clock, injected so tests can advance
        time without sleeping — NOT wall-clock, so patching ``datetime.now``
        has no effect on expiry.
        """
        self._org_role: "TTLCache[str, str]" = TTLCache(maxsize=maxsize, ttl=role_ttl, timer=timer)

    async def get_org_role(self, clerk_id: str) -> Union[str, Miss]:
        """The cached role for ``clerk_id``, or ``MISS`` if absent or expired."""
        role = self._org_role.get(clerk_id, MISS)
        if role is not MISS:
            logger.debug("org_role_cache_hit", clerk_id=clerk_id)
        return role

    async def set_org_role(self, clerk_id: str, role: str) -> None:
        """Cache a ``clerk_id -> role`` mapping for ``role_ttl`` seconds.

        ``role`` has Clerk's ``org:`` prefix already stripped.
        """
        self._org_role[clerk_id] = role

    async def invalidate_user(self, *, clerk_id: str) -> None:
        """Drop the cached role for one user."""
        self._org_role.pop(clerk_id, None)
        logger.debug("user_cache_invalidated", clerk_id=clerk_id)

    async def clear(self) -> None:
        """Empty the cache. Async form, for parity with the Redis seam."""
        self.reset()

    def reset(self) -> None:
        """Synchronous ``clear()`` for pytest fixtures and app lifespan.

        Not part of the Redis seam, and never to be called from a request path.
        It exists because a sync fixture calling ``clear()`` without awaiting
        would silently create a coroutine and clear nothing, leaking cache state
        across every test.
        """
        self._org_role.clear()


user_cache = UserCache()
