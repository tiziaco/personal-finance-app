"""Unit test fixtures — no DB, no network, no app startup."""

import pytest


@pytest.fixture(autouse=True)
def clear_user_cache():
    """Reset every user cache before and after each test.

    Sync on purpose: reset() is the non-async form. Calling the async clear()
    here without awaiting would create a coroutine, clear nothing, and leak
    cache state into every other unit test.
    """
    from app.modules.account.cache import user_cache
    from app.modules.supplier.cache import supplier_cache

    user_cache.reset()
    supplier_cache.reset()
    yield
    user_cache.reset()
    supplier_cache.reset()
