"""Tests for the Clerk webhook dispatcher and its account handlers.

Two invariants are load-bearing and tested explicitly:

1. Idempotency. There is no dedup table, so a replay within svix's
   five-minute tolerance must converge, not duplicate.
2. Never resurrect. An unknown clerk_id is ambiguous — the create event may
   not have landed, or the user may have been erased (anonymize_user
   rewrites clerk_id, so the two are indistinguishable). user.updated
   declines outright; user.created resolves the ambiguity by asking Clerk,
   and inserts only for a user Clerk still holds.

The membership payload carries public_user_data, which is what lets the
membership handlers create a missing user row themselves rather than
returning an error and relying on a retry. That is the answer to Clerk
delivering organization_membership.created before user.created.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from uuid_utils.compat import uuid7

from app.integrations.clerk import ClerkRateLimitError
from app.integrations.clerk.timestamps import UNSYNCED_EPOCH
from app.integrations.clerk.webhooks.schemas import (
    ClerkEvent,
    WebhookContext,
)
from app.modules.account import USER_OFFBOARDED, USER_SYNCED
from app.modules.account.models import User
from app.modules.account.webhooks import (
    handle_membership_created,
    handle_membership_deleted,
    handle_membership_updated,
    handle_user_created,
    handle_user_deleted,
    handle_user_updated,
    is_primary_email_verified,
    primary_email_from_payload,
)

pytestmark = pytest.mark.unit

NOW_MS = 1754000000000
NOW_DT = datetime.fromtimestamp(NOW_MS / 1000, tz=UTC)

USER_PAYLOAD = {
    "id": "user_abc",
    "first_name": "Ada",
    "last_name": "Lovelace",
    "image_url": "https://img.clerk.com/x",
    "public_metadata": {},
    "primary_email_address_id": "idn_1",
    "email_addresses": [
        {
            "id": "idn_2",
            "email_address": "other@example.com",
            "verification": {"status": "unverified"},
        },
        {
            "id": "idn_1",
            "email_address": "ada@example.com",
            "verification": {"status": "verified"},
        },
    ],
    "updated_at": NOW_MS,
}

MEMBERSHIP_PAYLOAD = {
    "id": "orgmem_1",
    "role": "org:supplier",
    "organization": {"id": "org_1", "name": "Acme"},
    "public_user_data": {
        "user_id": "user_abc",
        "identifier": "ada@example.com",
        "first_name": "Ada",
        "last_name": "Lovelace",
        "image_url": "https://img.clerk.com/x",
    },
    "public_metadata": {},
    "updated_at": 1754000000000,
}


def ctx(data: dict, session, event_type: str = "user.created") -> WebhookContext:
    """Wrap a raw payload in the context handlers now receive.

    Handlers read only `ctx.data` and `ctx.session`, so the event type and
    message id are placeholders except where a test asserts on them.
    """
    return WebhookContext(
        event=ClerkEvent(type=event_type, data=data),
        message_id="msg_test",
        session=session,
    )


@pytest.fixture
def session() -> AsyncMock:
    s = AsyncMock()
    s.add = MagicMock()
    return s


@pytest.fixture(autouse=True)
def clerk_has_the_user() -> AsyncMock:
    """Creating a row now confirms the user still exists in Clerk.

    Answering True by default keeps every other test exercising the path it
    was written for. The tests that care flip it, raise from it, or assert it
    was never asked.
    """
    with patch(
        "app.modules.account.service.user_service.exists_in_clerk",
        new=AsyncMock(return_value=True),
    ) as stub:
        yield stub


def existing_user(last_synced_at: datetime = NOW_DT) -> User:
    user = User(id=uuid7(), clerk_id="user_abc", email="ada@example.com", org_id="org_1")
    user.last_synced_at = last_synced_at
    return user


def make_user(org_id=None) -> User:
    return User(id=uuid7(), clerk_id="user_abc", email="ada@example.com", org_id=org_id)


def test_primary_email_picks_the_primary_address():
    assert primary_email_from_payload(USER_PAYLOAD) == "ada@example.com"


def test_primary_email_returns_none_when_absent():
    assert primary_email_from_payload({"email_addresses": []}) is None


def test_email_verified_reads_the_primary_address_only():
    assert is_primary_email_verified(USER_PAYLOAD) is True
    unverified = {
        **USER_PAYLOAD,
        "email_addresses": [{"id": "idn_1", "email_address": "a@b.c", "verification": {"status": "unverified"}}],
    }
    assert is_primary_email_verified(unverified) is False


async def test_user_created_inserts_with_null_org_and_clerk_timestamp(session):
    with (
        patch(
            "app.modules.account.webhooks.user_repository.get_by_clerk_id",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.modules.account.webhooks.user_repository.create_or_get",
            new=AsyncMock(return_value=existing_user()),
        ) as create,
        patch("app.modules.account.webhooks.events.publish", new=AsyncMock(return_value=1)),
    ):
        await handle_user_created(ctx(USER_PAYLOAD, session))

    kwargs = create.await_args.kwargs
    assert kwargs["org_id"] is None
    assert kwargs["email"] == "ada@example.com"
    assert kwargs["last_synced_at"] == NOW_DT


async def test_user_created_insert_seeds_epoch_when_timestamp_unusable(session):
    """Regression for the whole-branch review's Important 1: the insert
    branch must never pass last_synced_at=None through to the repository —
    UserRepository.create() falls back to datetime.now(UTC) for None, which
    is exactly the host-clock contamination _apply_profile and UNSYNCED_EPOCH
    both exist to prevent. A fast host clock would then make every
    subsequent user.updated for this row look stale forever."""
    payload_without_timestamp = {**USER_PAYLOAD, "updated_at": None}
    with (
        patch(
            "app.modules.account.webhooks.user_repository.get_by_clerk_id",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.modules.account.webhooks.user_repository.create_or_get",
            new=AsyncMock(return_value=existing_user()),
        ) as create,
        patch("app.modules.account.webhooks.events.publish", new=AsyncMock(return_value=1)),
    ):
        await handle_user_created(ctx(payload_without_timestamp, session))

    kwargs = create.await_args.kwargs
    assert kwargs["last_synced_at"] == UNSYNCED_EPOCH
    assert kwargs["last_synced_at"] is not None


async def test_user_created_declines_when_clerk_no_longer_has_the_user(session, clerk_has_the_user):
    """The resurrection guard: a delivery retried after the user was erased.

    anonymize_user() rewrites clerk_id, so the erased row is unreachable by
    the payload's id and looks like a user who never existed. Creating from
    the payload would put the erased email and names back in the database —
    the asymmetry handle_user_updated already declines on.
    """
    clerk_has_the_user.return_value = False
    with (
        patch(
            "app.modules.account.webhooks.user_repository.get_by_clerk_id",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.modules.account.webhooks.user_repository.create_or_get",
            new=AsyncMock(),
        ) as create,
        patch(
            "app.modules.account.webhooks.events.publish",
            new=AsyncMock(return_value=1),
        ) as publish,
    ):
        await handle_user_created(ctx(USER_PAYLOAD, session))

    create.assert_not_awaited()
    publish.assert_not_awaited()


async def test_user_created_propagates_an_inconclusive_clerk_error(session, clerk_has_the_user):
    """Only a 404 is an answer. Anything else must earn a redelivery.

    Swallowing a rate limit here would return 204, and svix would consider
    the delivery done — the user would be lost rather than retried.
    """
    clerk_has_the_user.side_effect = ClerkRateLimitError("rate limited", clerk_id="user_abc")
    with (
        patch(
            "app.modules.account.webhooks.user_repository.get_by_clerk_id",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.modules.account.webhooks.user_repository.create_or_get",
            new=AsyncMock(),
        ) as create,
        pytest.raises(ClerkRateLimitError),
    ):
        await handle_user_created(ctx(USER_PAYLOAD, session))

    create.assert_not_awaited()


async def test_user_created_on_existing_row_applies_as_update(session, clerk_has_the_user):
    user = existing_user(last_synced_at=NOW_DT - timedelta(hours=1))
    with (
        patch(
            "app.modules.account.webhooks.user_repository.get_by_clerk_id",
            new=AsyncMock(return_value=user),
        ),
        patch(
            "app.modules.account.webhooks.user_repository.create_or_get",
            new=AsyncMock(),
        ) as create,
        patch(
            "app.modules.account.webhooks.user_repository.update_from_clerk",
            new=AsyncMock(return_value=user),
        ) as update,
        patch("app.modules.account.webhooks.events.publish", new=AsyncMock(return_value=1)),
    ):
        await handle_user_created(ctx(USER_PAYLOAD, session))

    create.assert_not_awaited()
    update.assert_awaited_once()
    # The row was already there, so the existence check never runs. This is
    # what keeps the Clerk lookup at ~one call per new user; moving it above
    # get_by_clerk_id would make it one per delivery.
    clerk_has_the_user.assert_not_awaited()


async def test_user_created_without_an_email_is_skipped(session):
    with patch(
        "app.modules.account.webhooks.user_repository.create_or_get",
        new=AsyncMock(),
    ) as create:
        await handle_user_created(ctx({"id": "user_abc", "email_addresses": []}, session))

    create.assert_not_awaited()


async def test_user_updated_applies_the_profile(session):
    user = existing_user(last_synced_at=NOW_DT - timedelta(hours=1))
    with (
        patch(
            "app.modules.account.webhooks.user_repository.get_by_clerk_id",
            new=AsyncMock(return_value=user),
        ),
        patch(
            "app.modules.account.webhooks.user_repository.update_from_clerk",
            new=AsyncMock(return_value=user),
        ) as update,
    ):
        await handle_user_updated(ctx(USER_PAYLOAD, session))

    assert update.await_args.kwargs["first_name"] == "Ada"
    assert update.await_args.kwargs["last_synced_at"] == NOW_DT


async def test_user_updated_without_a_usable_timestamp_preserves_last_synced_at(session):
    """A payload with no usable updated_at must not advance last_synced_at
    to the host clock — that would contaminate the ordering guard for every
    later event on this row (see Task 6 fix round 1, Finding 2)."""
    stale_synced_at = NOW_DT - timedelta(hours=1)
    user = existing_user(last_synced_at=stale_synced_at)
    payload_without_timestamp = {**USER_PAYLOAD, "updated_at": None}
    with (
        patch(
            "app.modules.account.webhooks.user_repository.get_by_clerk_id",
            new=AsyncMock(return_value=user),
        ),
        patch(
            "app.modules.account.webhooks.user_repository.update_from_clerk",
            new=AsyncMock(return_value=user),
        ) as update,
    ):
        await handle_user_updated(ctx(payload_without_timestamp, session))

    # Passed through unchanged, not advanced to datetime.now(UTC).
    assert update.await_args.kwargs["last_synced_at"] == stale_synced_at


async def test_user_updated_never_creates_a_row(session):
    """The never-resurrect invariant."""
    with (
        patch(
            "app.modules.account.webhooks.user_repository.get_by_clerk_id",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.modules.account.webhooks.user_repository.create_or_get",
            new=AsyncMock(),
        ) as create,
        patch(
            "app.modules.account.webhooks.user_repository.update_from_clerk",
            new=AsyncMock(),
        ) as update,
    ):
        await handle_user_updated(ctx(USER_PAYLOAD, session))

    create.assert_not_awaited()
    update.assert_not_awaited()


async def test_stale_event_is_dropped(session):
    """An event older than what we have synced must not overwrite newer data."""
    user = existing_user(last_synced_at=NOW_DT + timedelta(hours=1))
    with (
        patch(
            "app.modules.account.webhooks.user_repository.get_by_clerk_id",
            new=AsyncMock(return_value=user),
        ),
        patch(
            "app.modules.account.webhooks.user_repository.update_from_clerk",
            new=AsyncMock(),
        ) as update,
    ):
        await handle_user_updated(ctx(USER_PAYLOAD, session))

    update.assert_not_awaited()


async def test_same_timestamp_still_applies(session):
    """Strict `<` — an identical timestamp is applied rather than risking a
    dropped distinct event. Safe because the write is idempotent."""
    user = existing_user(last_synced_at=NOW_DT)
    with (
        patch(
            "app.modules.account.webhooks.user_repository.get_by_clerk_id",
            new=AsyncMock(return_value=user),
        ),
        patch(
            "app.modules.account.webhooks.user_repository.update_from_clerk",
            new=AsyncMock(return_value=user),
        ) as update,
    ):
        await handle_user_updated(ctx(USER_PAYLOAD, session))

    update.assert_awaited_once()


async def test_user_deleted_runs_the_erasure_cascade(session):
    user = existing_user()
    with (
        patch(
            "app.modules.account.webhooks.user_repository.get_by_clerk_id",
            new=AsyncMock(return_value=user),
        ),
        patch(
            "app.modules.account.webhooks.user_service.erase_user",
            new=AsyncMock(),
        ) as erase,
    ):
        await handle_user_deleted(ctx({"id": "user_abc", "deleted": True}, session))

    erase.assert_awaited_once()


async def test_user_deleted_for_unknown_user_is_a_noop(session):
    """The echo of our own DELETE /me, and any replay, lands here."""
    with (
        patch(
            "app.modules.account.webhooks.user_repository.get_by_clerk_id",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.modules.account.webhooks.user_service.erase_user",
            new=AsyncMock(),
        ) as erase,
    ):
        await handle_user_deleted(ctx({"id": "user_abc", "deleted": True}, session))

    erase.assert_not_awaited()


async def test_no_handler_populates_the_role_cache(session):
    """Populating before commit could serve a value for a rolled-back
    transaction. Handlers invalidate; they never set."""
    user = existing_user(last_synced_at=NOW_DT - timedelta(hours=1))
    with (
        patch(
            "app.modules.account.webhooks.user_repository.get_by_clerk_id",
            new=AsyncMock(return_value=user),
        ),
        patch(
            "app.modules.account.webhooks.user_repository.update_from_clerk",
            new=AsyncMock(return_value=user),
        ),
        patch("app.modules.account.cache.UserCache.set_org_role", new=AsyncMock()) as set_role,
    ):
        await handle_user_updated(ctx(USER_PAYLOAD, session))

    set_role.assert_not_awaited()


async def test_created_sets_org_id_on_existing_user(session, clerk_has_the_user):
    user = make_user(org_id=None)
    with (
        patch(
            "app.modules.account.webhooks.user_repository.get_by_clerk_id",
            new=AsyncMock(return_value=user),
        ),
        patch(
            "app.modules.account.webhooks.user_repository.update_org_id",
            new=AsyncMock(return_value=user),
        ) as update_org,
        patch(
            "app.modules.account.webhooks.user_cache.invalidate_user",
            new=AsyncMock(),
        ),
        patch("app.modules.account.webhooks.events.publish", new=AsyncMock(return_value=1)),
    ):
        await handle_membership_created(ctx(MEMBERSHIP_PAYLOAD, session))

    update_org.assert_awaited_once()
    assert update_org.await_args.args[2] == "org_1"
    # The row was already there, so the existence check never runs. This is
    # what keeps the Clerk lookup at ~one call per new user; moving it above
    # get_by_clerk_id would make it one per delivery.
    clerk_has_the_user.assert_not_awaited()


async def test_created_builds_the_user_when_it_does_not_exist(session):
    """Handles organization_membership.created arriving before user.created,
    without relying on a retry."""
    created = make_user(org_id="org_1")
    with (
        patch(
            "app.modules.account.webhooks.user_repository.get_by_clerk_id",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.modules.account.webhooks.user_repository.create_or_get",
            new=AsyncMock(return_value=created),
        ) as create,
        patch(
            "app.modules.account.webhooks.user_cache.invalidate_user",
            new=AsyncMock(),
        ),
        patch("app.modules.account.webhooks.events.publish", new=AsyncMock(return_value=1)),
    ):
        await handle_membership_created(ctx(MEMBERSHIP_PAYLOAD, session))

    kwargs = create.await_args.kwargs
    assert kwargs["clerk_id"] == "user_abc"
    assert kwargs["email"] == "ada@example.com"
    assert kwargs["org_id"] == "org_1"


async def test_created_declines_when_clerk_no_longer_has_the_user(session, clerk_has_the_user):
    """The resurrection guard: a delivery retried after the user was erased.

    anonymize_user() rewrites clerk_id, so the erased row is unreachable by
    the payload's id and looks like a user who never existed. Creating from
    the payload would put the erased email and names back in the database.
    """
    clerk_has_the_user.return_value = False
    with (
        patch(
            "app.modules.account.webhooks.user_repository.get_by_clerk_id",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.modules.account.webhooks.user_repository.create_or_get",
            new=AsyncMock(),
        ) as create,
    ):
        await handle_membership_created(ctx(MEMBERSHIP_PAYLOAD, session))

    create.assert_not_awaited()


async def test_created_propagates_an_inconclusive_clerk_error(session, clerk_has_the_user):
    """Only a 404 is an answer. Anything else must earn a redelivery.

    Swallowing a rate limit here would return 204, and svix would consider
    the delivery done — the membership would be lost rather than retried.
    """
    clerk_has_the_user.side_effect = ClerkRateLimitError("rate limited", clerk_id="user_abc")
    with (
        patch(
            "app.modules.account.webhooks.user_repository.get_by_clerk_id",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.modules.account.webhooks.user_repository.create_or_get",
            new=AsyncMock(),
        ) as create,
        pytest.raises(ClerkRateLimitError),
    ):
        await handle_membership_created(ctx(MEMBERSHIP_PAYLOAD, session))

    create.assert_not_awaited()


async def test_created_seeds_last_synced_at_with_the_epoch_not_the_membership_clock(session):
    """Regression for Finding 1: seeding last_synced_at with the membership
    event's own updated_at (a clock newer than any pending user.created)
    would make the real user.created that follows look stale and get
    dropped by _apply_profile's ordering guard. The epoch is used instead
    precisely because it can never be newer than a genuine user event."""
    with (
        patch(
            "app.modules.account.webhooks.user_repository.get_by_clerk_id",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.modules.account.webhooks.user_repository.create_or_get",
            new=AsyncMock(return_value=make_user(org_id="org_1")),
        ) as create,
        patch(
            "app.modules.account.webhooks.user_cache.invalidate_user",
            new=AsyncMock(),
        ),
        patch("app.modules.account.webhooks.events.publish", new=AsyncMock(return_value=1)),
    ):
        await handle_membership_created(ctx(MEMBERSHIP_PAYLOAD, session))

    assert create.await_args.kwargs["last_synced_at"] == UNSYNCED_EPOCH


async def test_created_from_membership_does_not_suppress_the_user_created_that_follows(session):
    """End-to-end regression for Finding 1: a user row built by the
    membership handler must still accept the user.created payload that
    lands after it, rather than the two handlers' clocks fighting each
    other via User.last_synced_at."""
    row: dict = {}

    async def fake_create_or_get(**kwargs):
        row["user"] = User(
            id=uuid7(),
            clerk_id=kwargs["clerk_id"],
            email=kwargs["email"],
            org_id=kwargs["org_id"],
            last_synced_at=kwargs["last_synced_at"],
        )
        return row["user"]

    with (
        patch(
            "app.modules.account.webhooks.user_repository.get_by_clerk_id",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.modules.account.webhooks.user_repository.create_or_get",
            new=AsyncMock(side_effect=fake_create_or_get),
        ),
        patch(
            "app.modules.account.webhooks.user_cache.invalidate_user",
            new=AsyncMock(),
        ),
        patch("app.modules.account.webhooks.events.publish", new=AsyncMock(return_value=1)),
    ):
        await handle_membership_created(ctx(MEMBERSHIP_PAYLOAD, session))

    created_row = row["user"]

    user_created_payload = {
        "id": "user_abc",
        "primary_email_address_id": "idn_1",
        "email_addresses": [
            {
                "id": "idn_1",
                "email_address": "ada@example.com",
                "verification": {"status": "verified"},
            }
        ],
        "first_name": "Ada",
        "last_name": "Lovelace",
        "image_url": "https://img.clerk.com/x",
        "public_metadata": {},
        # Older than MEMBERSHIP_PAYLOAD's updated_at (1754000000000) — the
        # realistic case: the user was created before the membership event,
        # so its own timestamp is earlier, even though the membership event
        # is what our webhook processed first. If last_synced_at had been
        # seeded from the membership's clock instead of the epoch, this
        # older-but-genuine event_ts would look stale and get dropped.
        "updated_at": 1753000000000,
    }

    with (
        patch(
            "app.modules.account.webhooks.user_repository.get_by_clerk_id",
            new=AsyncMock(return_value=created_row),
        ),
        patch(
            "app.modules.account.webhooks.user_repository.update_from_clerk",
            new=AsyncMock(return_value=created_row),
        ) as update_from_clerk,
        patch("app.modules.account.webhooks.events.publish", new=AsyncMock(return_value=1)),
    ):
        await handle_user_created(ctx(user_created_payload, session))

    # The real payload must be applied, not dropped as stale.
    update_from_clerk.assert_awaited_once()
    assert update_from_clerk.await_args.kwargs["email"] == "ada@example.com"


async def test_created_without_an_identifier_is_skipped(session):
    payload = {**MEMBERSHIP_PAYLOAD, "public_user_data": {"user_id": "user_abc"}}
    with (
        patch(
            "app.modules.account.webhooks.user_repository.get_by_clerk_id",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.modules.account.webhooks.user_repository.create_or_get",
            new=AsyncMock(),
        ) as create,
    ):
        await handle_membership_created(ctx(payload, session))

    create.assert_not_awaited()


async def test_created_is_idempotent_when_org_already_matches(session):
    user = make_user(org_id="org_1")
    with (
        patch(
            "app.modules.account.webhooks.user_repository.get_by_clerk_id",
            new=AsyncMock(return_value=user),
        ),
        patch(
            "app.modules.account.webhooks.user_repository.update_org_id",
            new=AsyncMock(),
        ) as update_org,
        patch(
            "app.modules.account.webhooks.user_cache.invalidate_user",
            new=AsyncMock(),
        ),
        patch("app.modules.account.webhooks.events.publish", new=AsyncMock(return_value=1)),
    ):
        await handle_membership_created(ctx(MEMBERSHIP_PAYLOAD, session))

    update_org.assert_not_awaited()


async def test_updated_invalidates_the_role_cache(session):
    user = make_user(org_id="org_1")
    with (
        patch(
            "app.modules.account.webhooks.user_repository.get_by_clerk_id",
            new=AsyncMock(return_value=user),
        ),
        patch(
            "app.modules.account.webhooks.user_cache.invalidate_user",
            new=AsyncMock(),
        ) as invalidate,
    ):
        await handle_membership_updated(ctx(MEMBERSHIP_PAYLOAD, session))

    invalidate.assert_awaited_once_with(clerk_id="user_abc")


async def test_updated_never_populates_the_role_cache(session):
    """The event hands us the new role, but writing it before the request's
    commit could serve a value for a transaction that rolls back."""
    user = make_user(org_id="org_1")
    with (
        patch(
            "app.modules.account.webhooks.user_repository.get_by_clerk_id",
            new=AsyncMock(return_value=user),
        ),
        patch(
            "app.modules.account.webhooks.user_cache.invalidate_user",
            new=AsyncMock(),
        ),
        patch("app.modules.account.cache.UserCache.set_org_role", new=AsyncMock()) as set_role,
    ):
        await handle_membership_updated(ctx(MEMBERSHIP_PAYLOAD, session))

    set_role.assert_not_awaited()


async def test_deleted_clears_org_and_unlinks_the_supplier(session):
    user = make_user(org_id="org_1")
    with (
        patch(
            "app.modules.account.webhooks.user_repository.get_by_clerk_id",
            new=AsyncMock(return_value=user),
        ),
        patch(
            "app.modules.account.webhooks.events.publish",
            new=AsyncMock(return_value=1),
        ) as publish,
        patch(
            "app.modules.account.webhooks.user_cache.invalidate_user",
            new=AsyncMock(),
        ) as invalidate,
    ):
        await handle_membership_deleted(ctx(MEMBERSHIP_PAYLOAD, session))

    assert user.org_id is None
    publish.assert_awaited_once_with(USER_OFFBOARDED, session=session, user_id=user.id)
    invalidate.assert_awaited_once_with(clerk_id="user_abc")


async def test_deleted_for_the_users_current_org_still_unlinks(session):
    """The matching-org direction of the Finding 2 guard: a deletion whose
    org equals the user's current org_id is a genuine offboarding and must
    still clear org_id and unlink the supplier."""
    user = make_user(org_id="org_1")  # MEMBERSHIP_PAYLOAD's organization.id
    with (
        patch(
            "app.modules.account.webhooks.user_repository.get_by_clerk_id",
            new=AsyncMock(return_value=user),
        ),
        patch(
            "app.modules.account.webhooks.events.publish",
            new=AsyncMock(return_value=1),
        ) as publish,
        patch(
            "app.modules.account.webhooks.user_cache.invalidate_user",
            new=AsyncMock(),
        ) as invalidate,
    ):
        await handle_membership_deleted(ctx(MEMBERSHIP_PAYLOAD, session))

    assert user.org_id is None
    publish.assert_awaited_once_with(USER_OFFBOARDED, session=session, user_id=user.id)
    invalidate.assert_awaited_once()


async def test_deleted_for_a_user_with_no_org_still_unlinks(session):
    """Regression for the whole-branch review's Important 1: a NULL
    user.org_id must not be read as an unresolvable mismatch. The reachable
    path is a supplier invited via user.created (which sets org_id=None by
    design when linking from public_metadata.supplier_id) whose
    organizationMembership.created never landed or permanently failed —
    the user is later removed from the org and membership.deleted arrives
    with org_id still NULL. The prior guard (`event_org_id not in (None,
    user.org_id)`) treated any event org as a mismatch against a NULL
    user.org_id and no-opped, permanently stranding Supplier.contact_id
    (JIT repairs org_id but never contact_id). A NULL user.org_id can only
    mean created(B) never ran, so there is no "B" for this deletion to be
    misreading as a reversal — it must proceed as a genuine offboarding."""
    user = make_user(org_id=None)
    with (
        patch(
            "app.modules.account.webhooks.user_repository.get_by_clerk_id",
            new=AsyncMock(return_value=user),
        ),
        patch(
            "app.modules.account.webhooks.events.publish",
            new=AsyncMock(return_value=1),
        ) as publish,
        patch(
            "app.modules.account.webhooks.user_cache.invalidate_user",
            new=AsyncMock(),
        ) as invalidate,
    ):
        await handle_membership_deleted(ctx(MEMBERSHIP_PAYLOAD, session))  # org_1

    assert user.org_id is None
    publish.assert_awaited_once_with(USER_OFFBOARDED, session=session, user_id=user.id)
    invalidate.assert_awaited_once()


async def test_deleted_for_a_different_org_leaves_the_link_intact(session):
    """Regression for Finding 2: a stray deleted(A) landing after a
    created(B) for the same user must not undo B. Unlike the org loss
    alone (which JIT would repair), an unlink here would be permanent —
    JIT does not restore Supplier.contact_id."""
    user = make_user(org_id="org_2")  # already reassigned away from org_1
    with (
        patch(
            "app.modules.account.webhooks.user_repository.get_by_clerk_id",
            new=AsyncMock(return_value=user),
        ),
        patch(
            "app.modules.account.webhooks.events.publish",
            new=AsyncMock(return_value=1),
        ) as publish,
        patch(
            "app.modules.account.webhooks.user_cache.invalidate_user",
            new=AsyncMock(),
        ) as invalidate,
    ):
        await handle_membership_deleted(ctx(MEMBERSHIP_PAYLOAD, session))  # org_1

    assert user.org_id == "org_2"
    publish.assert_not_awaited()
    invalidate.assert_not_awaited()


async def test_deleted_is_idempotent(session):
    """A replay must converge, not fail on the second pass: the same event
    run twice against the same user object clears org_id both times, and
    USER_OFFBOARDED is published on both the first pass (a genuine
    offboarding) and the replay (a no-op supplier-side, but still reached —
    the handler does not special-case a replay).

    Regression for Important 3: the prior fixture used org_id=None, which
    exits at the org-mismatch guard before ever reaching the publish call —
    the assertion `user.org_id is None` was already true on entry, so no
    implementation could fail it."""
    user = make_user(org_id="org_1")  # MEMBERSHIP_PAYLOAD's organization.id
    with (
        patch(
            "app.modules.account.webhooks.user_repository.get_by_clerk_id",
            new=AsyncMock(return_value=user),
        ),
        patch(
            "app.modules.account.webhooks.events.publish",
            new=AsyncMock(return_value=1),
        ) as publish,
        patch(
            "app.modules.account.webhooks.user_cache.invalidate_user",
            new=AsyncMock(),
        ),
    ):
        await handle_membership_deleted(ctx(MEMBERSHIP_PAYLOAD, session))
        assert user.org_id is None
        publish.assert_awaited_once_with(USER_OFFBOARDED, session=session, user_id=user.id)

        # Replay: org_id is already None, so the guard's `user.org_id`
        # operand is falsy and the event still falls through to publish
        # (now a no-op supplier-side, but the handler does not know that
        # in advance).
        await handle_membership_deleted(ctx(MEMBERSHIP_PAYLOAD, session))
        assert user.org_id is None
        assert publish.await_count == 2


@pytest.mark.parametrize(
    "event_type,expected_handler",
    [
        ("organizationMembership.created", handle_membership_created),
        ("organization_membership.created", handle_membership_created),
        ("organizationMembership.updated", handle_membership_updated),
        ("organization_membership.updated", handle_membership_updated),
        ("organizationMembership.deleted", handle_membership_deleted),
        ("organization_membership.deleted", handle_membership_deleted),
    ],
)
async def test_both_event_spellings_dispatch(event_type, expected_handler):
    """A wrong registry key fails silently, so both spellings are registered.

    Regression for Finding 3: the original test only covered 2 of the 6
    registered keys and asserted mere presence (`is not None`), which a
    swapped handler on any of the other four lines would still pass. This
    checks all six keys against handler *identity*."""
    from app.modules.account.webhooks import clerk_dispatcher

    assert clerk_dispatcher._handlers.get(event_type) is expected_handler


async def test_deleted_for_unknown_user_is_a_noop(session):
    with (
        patch(
            "app.modules.account.webhooks.user_repository.get_by_clerk_id",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "app.modules.account.webhooks.events.publish",
            new=AsyncMock(return_value=1),
        ) as publish,
    ):
        await handle_membership_deleted(ctx(MEMBERSHIP_PAYLOAD, session))

    publish.assert_not_awaited()
