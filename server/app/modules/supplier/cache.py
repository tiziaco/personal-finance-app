"""In-memory cache of the user → supplier link.

``user_id -> supplier_id | None``. A cached ``None`` is a real value ("known
not linked"), which is why reads return ``MISS`` for absence.

Every public method is ``async def`` though nothing awaits: this is the seam
for a future Redis backend. ``TTLCache`` is not thread-safe and even reads
mutate its expiry bookkeeping; every access here is on the event loop thread.
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
from app.utils.cache import MISS, Miss

DEFAULT_MAXSIZE: Final[int] = 10_000
DEFAULT_TTL: Final[float] = 300.0  # supplier links change rarely


class SupplierCache:
    """Bounded, TTL-expiring cache of supplier links, keyed by internal user_id."""

    def __init__(
        self,
        *,
        maxsize: int = DEFAULT_MAXSIZE,
        ttl: float = DEFAULT_TTL,
        timer: Callable[[], float] = time.monotonic,
    ) -> None:
        """Build the cache. ``timer`` is a monotonic clock, injected so tests can advance time."""
        self._supplier_id: "TTLCache[str, Optional[str]]" = TTLCache(maxsize=maxsize, ttl=ttl, timer=timer)

    async def get_supplier_id(self, user_id: str) -> Union[str, None, Miss]:
        """The cached link: a supplier id, ``None`` (known not linked), or ``MISS``."""
        supplier_id = self._supplier_id.get(user_id, MISS)
        if supplier_id is not MISS:
            logger.debug("supplier_id_cache_hit", user_id=user_id, linked=supplier_id is not None)
        return supplier_id

    async def set_supplier_id(self, user_id: str, supplier_id: Optional[str]) -> None:
        """Cache a ``user_id -> supplier_id`` mapping. ``None`` is a deliberate negative entry."""
        self._supplier_id[user_id] = supplier_id

    async def invalidate_user(self, *, user_id: str) -> None:
        """Drop the cached link for one user."""
        self._supplier_id.pop(user_id, None)
        logger.debug("supplier_cache_invalidated", user_id=user_id)

    async def clear(self) -> None:
        """Empty the cache. Async form, for parity with the Redis seam."""
        self.reset()

    def reset(self) -> None:
        """Synchronous ``clear()`` for pytest fixtures; never from a request path."""
        self._supplier_id.clear()


supplier_cache = SupplierCache()
