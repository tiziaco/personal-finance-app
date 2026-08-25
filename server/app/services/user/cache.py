"""In-memory caches for the user service.

Two independent caches — different keys, different lifecycles, different TTLs:

* ``org_role``    — ``clerk_id -> role``. Feeds ``get_current_role()`` and
  therefore ``require_role()``, so a stale entry means a revoked permission
  stays honoured. Short TTL for that reason.
* ``supplier_id`` — ``user_id -> supplier_id | None``. A cached ``None`` is a
  real value ("this user is known not to be linked to any supplier"), which is
  why reads return a ``_MISS`` sentinel for absence instead of ``None``.

Every public method is ``async def`` even though nothing here awaits. This
module is the seam for a future Redis / cross-worker backend: swapping the
implementation must not touch a single call site.

Import rule: this module may import stdlib, ``cachetools`` and
``app.core.logging`` only. It must never import from ``app.services.user``,
``provider`` or ``service`` — the package ``__init__`` imports this module
first, so reaching back into a partially-initialised package would break the
import graph.

Concurrency: ``cachetools.TTLCache`` is not thread-safe, and even reads mutate
its internal expiry bookkeeping. Every access here happens on the event loop
thread; the only other threads in this process are the ``asyncio.to_thread``
workers wrapping the synchronous Clerk SDK, and none of them touch this module.
If that ever changes, guard each cache with a ``threading.RLock``.

Scope: single process. Under multiple workers each process holds its own copy,
so a TTL is a per-worker staleness bound, not a global one.
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
        """Build the caches.

        Args:
            maxsize: Max entries per cache; LRU eviction beyond it.
            ttl: Seconds to cache ``user_id -> supplier_id``.
            role_ttl: Seconds to cache ``clerk_id -> org_role``. Shorter than
                ``ttl`` because a stale role keeps a revoked permission alive.
            timer: Monotonic clock, injected so tests can advance time without
                sleeping. Note this is NOT wall-clock — patching
                ``datetime.now`` has no effect on expiry.
        """
        self._org_role: "TTLCache[str, str]" = TTLCache(
            maxsize=maxsize, ttl=role_ttl, timer=timer
        )
        self._supplier_id: "TTLCache[str, Optional[str]]" = TTLCache(
            maxsize=maxsize, ttl=ttl, timer=timer
        )

    # ------------------------------------------------------------------
    # org role — keyed by clerk_id
    # ------------------------------------------------------------------

    async def get_org_role(self, clerk_id: str) -> Union[str, _Miss]:
        """Get a cached org role.

        Args:
            clerk_id: The Clerk user ID.

        Returns:
            The role string, or ``_MISS`` if absent or expired.
        """
        role = self._org_role.get(clerk_id, _MISS)
        if role is not _MISS:
            logger.debug("org_role_cache_hit", clerk_id=clerk_id)
        return role

    async def set_org_role(self, clerk_id: str, role: str) -> None:
        """Cache a ``clerk_id -> role`` mapping for ``role_ttl`` seconds.

        Args:
            clerk_id: The Clerk user ID.
            role: The Clerk organisation role, ``org:`` prefix already stripped.
        """
        self._org_role[clerk_id] = role

    # ------------------------------------------------------------------
    # supplier link — keyed by internal user_id
    # ------------------------------------------------------------------

    async def get_supplier_id(self, user_id: str) -> Union[str, None, _Miss]:
        """Get a cached supplier link.

        Args:
            user_id: Internal ``User.id``.

        Returns:
            The supplier id, ``None`` (cached "known not linked"), or ``_MISS``
            when nothing is cached. Callers MUST branch on ``is not _MISS``.
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

        Args:
            user_id: Internal ``User.id``.
            supplier_id: The linked ``Supplier.id``, or ``None`` for "known not
                linked" — a deliberate negative cache.
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

        The two caches are keyed by different identifiers — org role by
        ``clerk_id``, supplier link by internal ``user_id`` — and this class
        keeps no reverse index on purpose (a second mapping would be a third
        thing to keep fresh). Each argument therefore clears only the cache it
        keys, and callers pass whichever identifiers they hold:

        * GDPR account deletion holds both -> pass both.
        * A supplier re-link knows only the displaced user's ``user_id`` ->
          pass that alone; their org role is unaffected anyway.

        Passing neither is a programming error. It is logged and ignored rather
        than raised, because the GDPR delete flow calls this *after* its commit
        and must not fail once the deletion has already succeeded.

        Args:
            clerk_id: Clears the cached org role.
            user_id: Clears the cached supplier link.
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

        Not part of the Redis seam: a future backend would make ``clear()`` do
        real I/O and this method would be dropped. Never call it from a request
        path. It exists because a sync autouse fixture calling ``clear()``
        without awaiting would silently create a coroutine and clear nothing,
        leaking cache state across every test.
        """
        self._org_role.clear()
        self._supplier_id.clear()


user_cache = UserCache()
