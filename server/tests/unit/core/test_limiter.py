"""The per-user rate-limit key."""

from unittest.mock import MagicMock

import pytest

from app.core.limiter import user_or_ip_key

pytestmark = pytest.mark.unit


def test_a_signed_in_caller_is_keyed_by_clerk_id():
    request = MagicMock()
    request.state.clerk_id = "user_123"
    assert user_or_ip_key(request) == "user:user_123"


def test_no_caller_falls_back_to_the_address():
    request = MagicMock()
    request.state.clerk_id = None
    request.client.host = "203.0.113.9"
    assert user_or_ip_key(request) == "203.0.113.9"
