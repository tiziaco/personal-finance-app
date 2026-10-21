"""Third-party libraries that log every request are silenced, and only they are.

Importing `app.core.logging` runs `setup_logging()` at module scope, which is
what these assert against.
"""

import logging

import pytest

import app.core.logging  # noqa: F401  - imported for its setup_logging() side effect

pytestmark = pytest.mark.unit


def test_the_openai_sdks_http_client_is_silenced_at_info() -> None:
    """openai>=3 is backed by httpx2, which logs one line per request at INFO.

    A leaf name, not the root `setup_logging` configures: the silencing relies on
    level inheritance, and asserting the root would pass even if that stopped holding.
    """
    assert not logging.getLogger("httpx2._client").isEnabledFor(logging.INFO)


def test_silencing_is_scoped_rather_than_a_global_floor() -> None:
    """Non-vacuity: the app's own records must still get through.

    Assumes `.env.test` sets LOG_LEVEL below WARNING, as it ships with DEBUG.
    """
    assert logging.getLogger().getEffectiveLevel() < logging.WARNING
