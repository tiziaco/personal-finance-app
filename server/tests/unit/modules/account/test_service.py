"""Tests for UserService.erase_user — the shared GDPR cascade.

Used by both DELETE /api/v1/auth/me and the user.deleted webhook, so the
ordering of its steps is contractual: checkpoints and memories must be
cleared before the row is anonymised, because anonymisation destroys the
identifiers those systems are keyed by.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.account import USER_ERASING
from app.modules.account.models import User
from app.modules.account.service import UserService, merge_clerk_metadata

pytestmark = pytest.mark.unit


def make_user() -> User:
    user = User(
        id="11111111-2222-3333-4444-555555555555",
        clerk_id="user_abc",
        email="person@example.com",
        org_id="org_1",
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
        patch("app.modules.account.service.user_cache.invalidate_user", new=AsyncMock()) as invalidate,
    ):
        await UserService().erase_user(user, session)

    mem.assert_awaited_once_with("11111111-2222-3333-4444-555555555555")
    publish.assert_awaited_once_with(USER_ERASING, session=session, user_id="11111111-2222-3333-4444-555555555555")
    invalidate.assert_awaited_once_with(clerk_id="user_abc")
    session.commit.assert_awaited_once()


async def test_erase_user_anonymizes_the_row(session):
    user = make_user()

    with (
        patch("app.modules.account.service.delete_user_memory", new=AsyncMock()),
        patch("app.modules.account.service.events.publish", new=AsyncMock(return_value=2)),
        patch("app.modules.account.service.user_cache.invalidate_user", new=AsyncMock()),
    ):
        await UserService().erase_user(user, session)

    assert user.clerk_id != "user_abc"
    assert user.email.endswith("@anonymized.local")
    assert user.org_id is None
    assert user.anonymized_at is not None


async def test_erase_user_invalidates_with_pre_anonymisation_clerk_id(session):
    """The cache is keyed by the original clerk_id, which anonymize_user destroys."""
    user = make_user()

    with (
        patch("app.modules.account.service.delete_user_memory", new=AsyncMock()),
        patch("app.modules.account.service.events.publish", new=AsyncMock(return_value=2)),
        patch("app.modules.account.service.user_cache.invalidate_user", new=AsyncMock()) as invalidate,
    ):
        await UserService().erase_user(user, session)

    assert invalidate.await_args.kwargs["clerk_id"] == "user_abc"


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
        patch("app.modules.account.service.user_cache.invalidate_user", new=AsyncMock()),
        patch.object(User, "anonymize_user", new=anonymize_mock),
    ):
        await UserService().erase_user(user, session)

    call_order = [call[0] for call in parent.mock_calls]
    assert call_order.index("delete_user_memory") < call_order.index("anonymize_user")
    assert call_order.index("publish") < call_order.index("anonymize_user")


async def test_erase_user_logs_the_subscriber_count(session):
    user = make_user()
    with (
        patch("app.modules.account.service.delete_user_memory", new=AsyncMock()),
        patch("app.modules.account.service.events.publish", new=AsyncMock(return_value=2)),
        patch("app.modules.account.service.user_cache.invalidate_user", new=AsyncMock()),
        patch("app.modules.account.service.logger") as logger,
    ):
        await UserService().erase_user(user, session)
    logger.info.assert_called_once_with("user_erased", user_id=user.id, subscriber_count=2)


async def test_erase_user_logs_an_error_when_no_module_handled_the_erasure(session):
    user = make_user()
    with (
        patch("app.modules.account.service.delete_user_memory", new=AsyncMock()),
        patch("app.modules.account.service.events.publish", new=AsyncMock(return_value=0)),
        patch("app.modules.account.service.user_cache.invalidate_user", new=AsyncMock()),
        patch("app.modules.account.service.logger") as logger,
    ):
        await UserService().erase_user(user, session)
    logger.error.assert_called_once_with("user_erasing_had_no_subscribers", user_id=user.id)


class FakeMembership:
    def __init__(self, metadata):
        self.public_metadata = metadata


class FakeClerkUser:
    def __init__(self, top, memberships):
        self.public_metadata = top
        self.organization_memberships = memberships


def test_merge_prefers_top_level_over_membership_metadata():
    clerk_user = FakeClerkUser({"supplier_id": "top"}, [FakeMembership({"supplier_id": "membership"})])
    assert merge_clerk_metadata(clerk_user)["supplier_id"] == "top"


def test_merge_falls_back_to_membership_metadata():
    clerk_user = FakeClerkUser({}, [FakeMembership({"supplier_id": "membership", "replace": True})])
    merged = merge_clerk_metadata(clerk_user)
    assert merged["supplier_id"] == "membership"
    assert merged["replace"] is True


def test_merge_tolerates_missing_attributes():
    class Bare:
        pass

    assert merge_clerk_metadata(Bare()) == {}
