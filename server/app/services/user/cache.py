"""In-memory caches for the user service.

Two independent caches — different keys, different lifecycles, different TTLs:

* ``org_role``    — ``clerk_id -> role``. Feeds ``get_current_role()`` and so
  ``require_role()``: a stale entry keeps a revoked permission alive, hence the
  short TTL.
* ``supplier_id`` — ``user_id -> supplier_id | None``. A cached ``None`` is a
  real value ("known not linked"), which is why reads return a ``_MISS``
  sentinel for absence instead of ``None``.

Every public method is ``async def`` though nothing awaits: this module is the
seam for a future Redis backend, and swapping it must not touch a call site.

Import rule: stdlib, ``cachetools`` and ``app.core.logging`` only. The package
``__init__`` imports this module first, so importing from ``app.services.user``,
``provider`` or ``service`` here would break the import graph.

``TTLCache`` is not thread-safe and even reads mutate its expiry bookkeeping.
Every access here is on the event loop thread; if that changes, guard each cache
with a ``threading.RLock``. Caches are per-process, so a TTL bounds staleness
per worker, not globally.
"""

import time
from typing import (
    Callable,
    Final,
    Optional,
    Union,
)

from cachetools import TTLCache

from app.core.logging import logger


class _Miss:
    """Sentinel type meaning "no entry in the cache".

    Distinct from ``None``, which is a legitimate cached supplier id. A class
    rather than a bare ``object()`` so it can appear in type hints. Deliberately
    defines no ``__bool__``: the protocol is ``is not _MISS``, never truthiness.
    """

    __slots__ = ()

    def __repr__(self) -> str:
        """Return a readable marker for logs and test failure output."""
        return "<MISS>"


_MISS: Final[_Miss] = _Miss()

DEFAULT_MAXSIZE: Final[int] = 10_000
DEFAULT_TTL: Final[float] = 300.0  # supplier links — change rarely
DEFAULT_ROLE_TTL: Final[float] = 60.0  # org roles — feed authorization


class UserCache:
    """Bounded, TTL-expiring caches for user-derived auth data."""

    def __init__(
        self,
        *,
        maxsize: int = DEFAULT_MAXSIZE,
        ttl: float = DEFAULT_TTL,
        role_ttl: float = DEFAULT_ROLE_TTL,
        timer: Callable[[], float] = time.monotonic,
    ) -> None:
        """Build the caches. ``maxsize`` is per cache; LRU eviction beyond it.

        ``role_ttl`` is shorter than ``ttl`` because a stale role keeps a
        revoked permission alive. ``timer`` is a monotonic clock, injected so
        tests can advance time without sleeping — NOT wall-clock, so patching
        ``datetime.now`` has no effect on expiry.
        """
        self._org_role: "TTLCache[str, str]" = TTLCache(maxsize=maxsize, ttl=role_ttl, timer=timer)
        self._supplier_id: "TTLCache[str, Optional[str]]" = TTLCache(maxsize=maxsize, ttl=ttl, timer=timer)

    # ------------------------------------------------------------------
    # org role — keyed by clerk_id
    # ------------------------------------------------------------------

    async def get_org_role(self, clerk_id: str) -> Union[str, _Miss]:
        """The cached role for ``clerk_id``, or ``_MISS`` if absent or expired."""
        role = self._org_role.get(clerk_id, _MISS)
        if role is not _MISS:
            logger.debug("org_role_cache_hit", clerk_id=clerk_id)
        return role

    async def set_org_role(self, clerk_id: str, role: str) -> None:
        """Cache a ``clerk_id -> role`` mapping for ``role_ttl`` seconds.

        ``role`` has Clerk's ``org:`` prefix already stripped.
        """
        self._org_role[clerk_id] = role

    # ------------------------------------------------------------------
    # supplier link — keyed by internal user_id
    # ------------------------------------------------------------------

    async def get_supplier_id(self, user_id: str) -> Union[str, None, _Miss]:
        """Get a cached supplier link.

        Returns the supplier id, ``None`` (cached "known not linked"), or
        ``_MISS`` when nothing is cached. Callers MUST branch on
        ``is not _MISS``.
        """
        supplier_id = self._supplier_id.get(user_id, _MISS)
        if supplier_id is not _MISS:
            logger.debug(
                "supplier_id_cache_hit",
                user_id=user_id,
                linked=supplier_id is not None,
            )
        return supplier_id

    async def set_supplier_id(self, user_id: str, supplier_id: Optional[str]) -> None:
        """Cache a ``user_id -> supplier_id`` mapping for ``ttl`` seconds.

        A ``None`` supplier_id is a deliberate negative cache, not an erasure.
        """
        self._supplier_id[user_id] = supplier_id

    # ------------------------------------------------------------------
    # invalidation
    # ------------------------------------------------------------------

    async def invalidate_user(
        self,
        *,
        clerk_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> None:
        """Drop every cached entry for one user.

        The caches key on different identifiers — org role on ``clerk_id``,
        supplier link on ``user_id`` — and there is deliberately no reverse
        index, so each argument clears only the cache it keys. Callers pass
        whichever identifiers they hold: GDPR deletion has both, a supplier
        re-link only the displaced user's ``user_id``.

        Passing neither is a programming error, logged rather than raised: the
        GDPR delete flow calls this *after* its commit and must not fail once
        the deletion has already succeeded.
        """
        if clerk_id is None and user_id is None:
            logger.warning("user_cache_invalidate_noop")
            return
        if clerk_id is not None:
            self._org_role.pop(clerk_id, None)
        if user_id is not None:
            self._supplier_id.pop(user_id, None)
        logger.debug("user_cache_invalidated", clerk_id=clerk_id, user_id=user_id)

    async def clear(self) -> None:
        """Empty every cache. Async form, for parity with the Redis seam."""
        self.reset()

    def reset(self) -> None:
        """Synchronous ``clear()`` for pytest fixtures and app lifespan.

        Not part of the Redis seam, and never to be called from a request path.
        It exists because a sync fixture calling ``clear()`` without awaiting
        would silently create a coroutine and clear nothing, leaking cache state
        across every test.
        """
        self._org_role.clear()
        self._supplier_id.clear()


user_cache = UserCache()
