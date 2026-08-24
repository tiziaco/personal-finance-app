"""Unit test fixtures — no DB, no network, no app startup."""

import pytest


@pytest.fixture(autouse=True)
def clear_user_cache():
    """Clear the user provider cache before/after each test."""
    from app.services.user.provider import _clerk_id_cache

    _clerk_id_cache.clear()
    yield
    _clerk_id_cache.clear()
