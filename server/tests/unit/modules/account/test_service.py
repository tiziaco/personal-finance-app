"""Tests for UserService.erase_user — the shared GDPR cascade.

Used by both DELETE /api/v1/auth/me and the user.deleted webhook, so the
ordering of its steps is contractual: checkpoints and memories must be
cleared before the row is anonymised, because anonymisation destroys the
identifiers those systems are keyed by.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.account import USER_ERASING
from app.modules.account.models import User
from app.modules.account.service import UserService, clerk_public_metadata

pytestmark = pytest.mark.unit

USER_ID = uuid.UUID("0199a8b0-0000-7000-8000-000000000001")


def make_user() -> User:
    user = User(
        id=USER_ID,
        clerk_id="user_abc",
        email="person@example.com",
    )
    return user


@pytest.fixture
def session() -> AsyncMock:
    s = AsyncMock()
    s.add = MagicMock()
    return s


async def test_erase_user_runs_full_cascade(session):
    user = make_user()

    with (
        patch("app.modules.account.service.delete_user_memory", new=AsyncMock()) as mem,
        patch("app.modules.account.service.events.publish", new=AsyncMock(return_value=2)) as publish,
    ):
        await UserService.erase_user(session, user)

    mem.assert_awaited_once_with(USER_ID)
    publish.assert_awaited_once_with(USER_ERASING, session=session, user_id=USER_ID)
    # The request's DbSession commits the cascade; erase_user never does.
    session.commit.assert_not_awaited()


async def test_erase_user_anonymizes_the_row(session):
    user = make_user()

    with (
        patch("app.modules.account.service.delete_user_memory", new=AsyncMock()),
        patch("app.modules.account.service.events.publish", new=AsyncMock(return_value=2)),
    ):
        await UserService.erase_user(session, user)

    assert user.clerk_id != "user_abc"
    assert user.email.endswith("@anonymized.local")
    assert user.anonymized_at is not None


async def test_erase_user_clears_checkpoints_and_memory_before_anonymising(session):
    """Step order is contractual, not incidental.

    anonymize_user() rewrites clerk_id, and the LangGraph checkpoint store and
    mem0 memory are both keyed by identifiers that exist only before that
    rewrite. If anonymize_user() ever ran first, checkpoint/memory cleanup
    would silently no-op against the wrong (or already-gone) identifiers —
    a regression the outcome-based tests above would NOT catch, since they
    only assert final call counts and end state, not sequence. This is also
    the exact guarantee the user.deleted webhook handler will depend on.
    """
    user = make_user()

    parent = MagicMock()

    delete_memory_mock = AsyncMock()
    parent.attach_mock(delete_memory_mock, "delete_user_memory")

    anonymize_mock = MagicMock()
    parent.attach_mock(anonymize_mock, "anonymize_user")

    publish_mock = AsyncMock(return_value=2)
    parent.attach_mock(publish_mock, "publish")

    with (
        patch("app.modules.account.service.delete_user_memory", new=delete_memory_mock),
        patch("app.modules.account.service.events.publish", new=publish_mock),
        patch.object(User, "anonymize_user", new=anonymize_mock),
    ):
        await UserService.erase_user(session, user)

    call_order = [call[0] for call in parent.mock_calls]
    assert call_order.index("delete_user_memory") < call_order.index("anonymize_user")
    assert call_order.index("publish") < call_order.index("anonymize_user")


async def test_erase_user_logs_the_subscriber_count(session):
    user = make_user()
    with (
        patch("app.modules.account.service.delete_user_memory", new=AsyncMock()),
        patch("app.modules.account.service.events.publish", new=AsyncMock(return_value=2)),
        patch("app.modules.account.service.logger") as logger,
    ):
        await UserService.erase_user(session, user)
    logger.info.assert_called_once_with("user_erased", user_id=user.id, subscriber_count=2)


async def test_erase_user_logs_an_error_when_no_module_handled_the_erasure(session):
    user = make_user()
    with (
        patch("app.modules.account.service.delete_user_memory", new=AsyncMock()),
        patch("app.modules.account.service.events.publish", new=AsyncMock(return_value=0)),
        patch("app.modules.account.service.logger") as logger,
    ):
        await UserService.erase_user(session, user)
    logger.error.assert_called_once_with("user_erasing_had_no_subscribers", user_id=user.id)


def test_public_metadata_is_returned_as_a_dict():
    assert clerk_public_metadata(SimpleNamespace(public_metadata={"plan": "free"})) == {"plan": "free"}


def test_public_metadata_tolerates_missing_and_malformed_values():
    assert clerk_public_metadata(SimpleNamespace()) == {}
    assert clerk_public_metadata(SimpleNamespace(public_metadata=None)) == {}
    assert clerk_public_metadata(SimpleNamespace(public_metadata="not-a-dict")) == {}
