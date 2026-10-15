"""The import's reaction to USER_ERASING."""

import pytest

from app.core.events import events
from app.modules.account import USER_ERASING
from app.modules.transaction.imports import handlers

pytestmark = pytest.mark.unit


def test_subscribes_inline_to_user_erasing():
    matches = [s for s in events.subscriptions(USER_ERASING) if s.handler is handlers.erase_imports_on_user_erasing]
    assert matches, "erase_imports_on_user_erasing is not subscribed to USER_ERASING"
    assert matches[0].inline
