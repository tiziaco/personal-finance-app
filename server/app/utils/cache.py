"""The cache-miss sentinel shared by the per-module caches.

A cached ``None`` is a legitimate value ("known not linked"), so reads return
``MISS`` for absence instead of ``None``. A class rather than a bare
``object()`` so it can appear in type hints; deliberately no ``__bool__``: the
protocol is ``is not MISS``, never truthiness.
"""

from typing import Final


class Miss:
    """Sentinel type meaning "no entry in the cache"."""

    __slots__ = ()

    def __repr__(self) -> str:
        """Return a readable marker for logs and test failure output."""
        return "<MISS>"


MISS: Final[Miss] = Miss()
