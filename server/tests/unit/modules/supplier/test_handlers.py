"""The supplier module's reactions to account events (architecture §5)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.events import events
from app.modules.account import USER_ERASING, USER_OFFBOARDED, USER_SYNCED
from app.modules.supplier import handlers

pytestmark = pytest.mark.unit


@pytest.fixture
def session() -> AsyncMock:
    s = AsyncMock()
    s.add = MagicMock()
    return s


def test_subscribes_inline_to_the_three_account_events():
    for handler, event in (
        (handlers.link_on_user_synced, USER_SYNCED),
        (handlers.unlink_on_user_erasing, USER_ERASING),
        (handlers.unlink_on_user_offboarded, USER_OFFBOARDED),
    ):
        matches = [s for s in events.subscriptions(event) if s.handler is handler]
        assert matches, f"{handler.__qualname__} is not subscribed to {event}"
        assert matches[0].inline, f"{handler.__qualname__} must be subscribed inline"


async def test_synced_links_from_the_merged_metadata(session):
    with patch("app.modules.supplier.handlers.supplier_service.link_from_metadata", new=AsyncMock()) as link:
        await handlers.link_on_user_synced(session=session, user_id="u1", metadata={"supplier_id": "sup_1"})
    link.assert_awaited_once_with(session, "u1", {"supplier_id": "sup_1"})


async def test_erasing_unlinks_and_drops_the_cached_link_even_when_nothing_was_linked(session):
    with (
        patch(
            "app.modules.supplier.handlers.supplier_service.unlink_contact", new=AsyncMock(return_value=None)
        ) as unlink,
        patch("app.modules.supplier.handlers.supplier_cache.invalidate_user", new=AsyncMock()) as invalidate,
    ):
        await handlers.unlink_on_user_erasing(session=session, user_id="u1")
    unlink.assert_awaited_once_with(session, "u1")
    invalidate.assert_awaited_once_with(user_id="u1")


async def test_offboarded_unlinks_and_logs_only_when_a_supplier_was_unlinked(session):
    with (
        patch("app.modules.supplier.handlers.supplier_service.unlink_contact", new=AsyncMock(return_value="sup_1")),
        patch("app.modules.supplier.handlers.supplier_cache.invalidate_user", new=AsyncMock()),
        patch("app.modules.supplier.handlers.logger") as logger,
    ):
        await handlers.unlink_on_user_offboarded(session=session, user_id="u1")
    logger.info.assert_called_once_with("supplier_unlinked_on_offboarding", user_id="u1", supplier_id="sup_1")


async def test_offboarded_does_not_log_an_unlink_when_there_was_none(session):
    with (
        patch("app.modules.supplier.handlers.supplier_service.unlink_contact", new=AsyncMock(return_value=None)),
        patch("app.modules.supplier.handlers.supplier_cache.invalidate_user", new=AsyncMock()) as invalidate,
        patch("app.modules.supplier.handlers.logger") as logger,
    ):
        await handlers.unlink_on_user_offboarded(session=session, user_id="u1")
    logger.info.assert_not_called()
    invalidate.assert_awaited_once_with(user_id="u1")
