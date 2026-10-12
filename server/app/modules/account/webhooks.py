"""Clerk webhook dispatch and the account's handlers for it.

Dispatch and handlers sit together in the module that owns the rows they
write (architecture D2): the adapter (`app.integrations.clerk.webhooks`)
verifies and parses, this file decides what a Clerk event means for an
account. Handlers are registered by event type rather than selected with a
chain of conditionals, so each one stays independently testable and the
registry doubles as the list of events this app subscribes to.

Every handler must be idempotent. There is no dedup table: svix supplies
signature validity and a five-minute timestamp tolerance, and within that
window a replay must converge rather than duplicate.

Ordering: Clerk guarantees none. The user.* handlers compare the payload's
`updated_at` against `User.last_synced_at` and drop the stale one; the
membership handlers deliberately do not (reusing that column would conflate
two clocks). The one place a membership handler touches `last_synced_at` is
seeding UNSYNCED_EPOCH on a row it creates, so a *real* user.* event is never
mistaken for stale.
"""

from datetime import datetime
from typing import (
    Awaitable,
    Callable,
    Dict,
    Optional,
)

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import events
from app.core.logging import logger
from app.integrations.clerk.timestamps import UNSYNCED_EPOCH, clerk_timestamp_to_datetime
from app.integrations.clerk.webhooks import WebhookContext
from app.modules.account.cache import user_cache
from app.modules.account.models import User
from app.modules.account.repository import user_repository
from app.modules.account.service import USER_OFFBOARDED, USER_SYNCED, user_service

WebhookHandler = Callable[[WebhookContext], Awaitable[None]]


class ClerkEventDispatcher:
    """Routes verified Clerk events to their handlers."""

    def __init__(self) -> None:
        """Build an empty registry."""
        self._handlers: Dict[str, WebhookHandler] = {}

    def register(self, event_type: str, handler: WebhookHandler) -> None:
        """Register a handler for one Clerk event type.

        Args:
            event_type: The Clerk event string, e.g. "user.created".
            handler: Coroutine taking one WebhookContext.
        """
        self._handlers[event_type] = handler

    async def dispatch(self, ctx: WebhookContext) -> None:
        """Run the handler registered for this event's type.

        An unregistered type is logged and ignored. It must not raise: Clerk
        retries failed deliveries and disables endpoints that keep failing, so
        an error here would eventually cost us the events we do handle.

        Both log lines carry svix's message id, so a line here can be matched
        against the delivery of the same id in Clerk's dashboard.

        Args:
            ctx: The verified event, its delivery id, and the DB session.
        """
        handler = self._handlers.get(ctx.event.type)

        if handler is None:
            logger.info(
                "webhook_event_unhandled",
                event_type=ctx.event.type,
                message_id=ctx.message_id,
            )
            return

        await handler(ctx)
        logger.info(
            "webhook_event_processed",
            event_type=ctx.event.type,
            message_id=ctx.message_id,
        )


def primary_email_from_payload(data: dict) -> Optional[str]:
    """Extract the primary email address from a Clerk user payload.

    The SDK helper takes an SDK object; webhook payloads are plain dicts, so
    this is the dict equivalent.

    Args:
        data: A Clerk user payload.

    Returns:
        The primary email address, or None if the payload has none.
    """
    primary_id = data.get("primary_email_address_id")
    for entry in data.get("email_addresses") or []:
        if entry.get("id") == primary_id:
            return entry.get("email_address")
    return None


def is_primary_email_verified(data: dict) -> bool:
    """Report whether the primary email address is verified.

    Args:
        data: A Clerk user payload.

    Returns:
        True only when the primary address exists and is verified.
    """
    primary_id = data.get("primary_email_address_id")
    for entry in data.get("email_addresses") or []:
        if entry.get("id") == primary_id:
            return (entry.get("verification") or {}).get("status") == "verified"
    return False


async def _apply_profile(
    session: AsyncSession,
    user: User,
    data: dict,
    event_ts: Optional[datetime],
) -> None:
    """Apply a profile snapshot, unless the event predates our last sync.

    Clerk guarantees no ordering, so two updates can arrive reversed. The
    comparison is strict: an identical timestamp is applied rather than
    dropped, because the write is idempotent and a same-millisecond distinct
    event is the worse thing to lose.

    Args:
        session: DB session.
        user: The user to update.
        data: The Clerk user payload.
        event_ts: The payload's updated_at, or None if absent/unusable.
    """
    if event_ts is not None and event_ts < user.last_synced_at:
        logger.info(
            "webhook_event_stale",
            clerk_id=user.clerk_id,
            event_ts=event_ts.isoformat(),
            last_synced_at=user.last_synced_at.isoformat(),
        )
        return

    # UserRepository.update_from_clerk() falls back to the host clock (now())
    # whenever last_synced_at is None — that fallback exists for the JIT path,
    # which has no Clerk event to draw a timestamp from. On the webhook path
    # an absent/unusable event_ts must NOT trigger that fallback: writing a
    # host-clock value into last_synced_at would contaminate this same
    # ordering guard for every later event on this row (a fast local clock
    # would then make every future legitimate event look stale forever). So
    # when we have no Clerk timestamp, pass the row's current value through
    # unchanged rather than letting the repository advance it to now().
    await user_repository.update_from_clerk(
        session=session,
        user=user,
        email=primary_email_from_payload(data),
        first_name=data.get("first_name"),
        last_name=data.get("last_name"),
        avatar_url=data.get("image_url"),
        email_verified=is_primary_email_verified(data),
        last_synced_at=event_ts or user.last_synced_at,
    )


async def handle_user_created(ctx: WebhookContext) -> None:
    """Create the user row, or apply the payload as an update if it exists.

    Inserts with a null org_id: Clerk's user.created payload carries no
    organisation, because membership is a separate resource with its own
    events. organization_membership.created fills it in, and JIT fills it in
    at first login as a second backstop.

    Safe to handle unconditionally only because the Clerk instance is
    invitation-only. If public sign-up is ever enabled this becomes an
    unauthenticated row-creation vector and must be gated on membership.

    Insertion is additionally gated on the user still existing in Clerk.
    anonymize_user() rewrites clerk_id, so an erased user is indistinguishable
    from one who never existed — the asymmetry handle_user_updated declines on.
    A delivery redelivered after the deletion would otherwise re-insert the
    payload's email and names.

    Args:
        ctx: The verified event, its delivery id, and the DB session.
    """
    data = ctx.data
    session = ctx.session
    clerk_id = data.get("id")
    email = primary_email_from_payload(data)

    if not clerk_id or not email:
        logger.warning("webhook_user_created_incomplete", clerk_id=clerk_id, has_email=bool(email))
        return

    event_ts = clerk_timestamp_to_datetime(data.get("updated_at"))
    user = await user_repository.get_by_clerk_id(session, clerk_id)

    if user is None:
        # Deliberately below get_by_clerk_id: the common case (the row is
        # already there) spends no Clerk call, so this costs roughly one
        # call per genuinely new user rather than one per delivery.
        if not await user_service.exists_in_clerk(clerk_id):
            logger.info("webhook_user_created_absent_in_clerk", clerk_id=clerk_id)
            return

        user = await user_repository.create_or_get(
            session=session,
            clerk_id=clerk_id,
            email=email,
            org_id=None,
            first_name=data.get("first_name"),
            last_name=data.get("last_name"),
            avatar_url=data.get("image_url"),
            email_verified=is_primary_email_verified(data),
            # Never let UserRepository.create()'s None fallback write the
            # host clock here: that is the exact contamination _apply_profile
            # and UNSYNCED_EPOCH both exist to prevent. When event_ts is absent or
            # unusable, seed the epoch instead so a fast host clock can never
            # make a later, genuine event look stale.
            last_synced_at=event_ts or UNSYNCED_EPOCH,
        )
        logger.info("webhook_user_created", user_id=user.id, clerk_id=clerk_id)
    else:
        # A replay, or a create arriving after an update. Converge rather
        # than conflict.
        await _apply_profile(session, user, data, event_ts)

    await events.publish(USER_SYNCED, session=session, user_id=user.id, metadata=data.get("public_metadata") or {})


async def handle_user_updated(ctx: WebhookContext) -> None:
    """Apply a profile update. Never creates a row.

    An unknown clerk_id has two indistinguishable causes: the create event has
    not landed, or the user was erased — anonymize_user() rewrites clerk_id,
    so an erased user looks exactly like one who never existed. Creating here
    would resurrect deleted users, so the handler declines.

    Args:
        ctx: The verified event, its delivery id, and the DB session.
    """
    data = ctx.data
    session = ctx.session
    clerk_id = data.get("id")
    if not clerk_id:
        logger.warning("webhook_user_updated_incomplete")
        return

    user = await user_repository.get_by_clerk_id(session, clerk_id)
    if user is None:
        logger.warning("webhook_user_updated_unknown", clerk_id=clerk_id)
        return

    await _apply_profile(session, user, data, clerk_timestamp_to_datetime(data.get("updated_at")))


async def handle_user_deleted(ctx: WebhookContext) -> None:
    """Run the full GDPR erasure cascade.

    Anonymising the row alone would orphan LangGraph checkpoints and mem0
    memories with no user row left pointing at them, so nothing would ever
    clean them up — a hole that opens only on the dashboard-initiated path.

    No ordering guard: the payload is a DeletedObjectJSON with no updated_at,
    and deletion is self-protecting. After erasure clerk_id is rewritten, so
    any later event for the original id finds no row.

    Args:
        ctx: The verified event, its delivery id, and the DB session.
    """
    data = ctx.data
    session = ctx.session
    clerk_id = data.get("id")
    if not clerk_id:
        logger.warning("webhook_user_deleted_incomplete")
        return

    user = await user_repository.get_by_clerk_id(session, clerk_id)
    if user is None:
        # Either the echo of our own DELETE /me, or a replay. Both benign.
        logger.info("webhook_user_deleted_noop", clerk_id=clerk_id)
        return

    await user_service.erase_user(session, user)
    logger.info("webhook_user_erased", clerk_id=clerk_id)


def _organization_id(data: dict) -> Optional[str]:
    """Read the organisation id from a membership payload."""
    return (data.get("organization") or {}).get("id")


async def _resolve_or_create_user(data: dict, session: AsyncSession) -> Optional[User]:
    """Find the membership's user, creating the row if it is missing.

    The payload's public_user_data carries the clerk id, email, names and
    avatar, so a membership event arriving before user.created can build the
    row itself rather than erroring and waiting for a retry.

    Building it is gated on one Clerk lookup. anonymize_user() rewrites
    clerk_id, so an erased user is indistinguishable from one who never
    existed, and a delivery redelivered after the deletion would otherwise
    re-insert the payload's email and names. Only a 404 declines — every
    other Clerk error propagates, so an inconclusive answer earns a
    redelivery rather than a row.

    The new row's last_synced_at is seeded to UNSYNCED_EPOCH, not this event's
    own timestamp: the two are ordered by different clocks, and a membership
    arriving before user.created has the later one by definition. Writing it
    would make the user.created that follows look stale and be dropped by
    _apply_profile's ordering guard — the exact failure this path exists to
    avoid.

    Returns None if the payload lacks what a row requires.
    """
    public_user_data = data.get("public_user_data") or {}
    clerk_id = public_user_data.get("user_id")

    if not clerk_id:
        logger.warning("webhook_membership_missing_user_id", membership_id=data.get("id"))
        return None

    user = await user_repository.get_by_clerk_id(session, clerk_id)
    if user is not None:
        return user

    email = public_user_data.get("identifier")
    if not email:
        logger.warning("webhook_membership_missing_email", clerk_id=clerk_id)
        return None

    # Deliberately last: an existing row and a payload we would reject both
    # cost no Clerk call, so this is roughly one call per genuinely new user
    # rather than one per delivery.
    if not await user_service.exists_in_clerk(clerk_id):
        logger.info("webhook_membership_user_absent_in_clerk", clerk_id=clerk_id)
        return None

    user = await user_repository.create_or_get(
        session=session,
        clerk_id=clerk_id,
        email=email,
        org_id=_organization_id(data),
        first_name=public_user_data.get("first_name"),
        last_name=public_user_data.get("last_name"),
        avatar_url=public_user_data.get("image_url"),
        # The membership payload does not report verification status. Start
        # false; user.created or user.updated corrects it.
        email_verified=False,
        last_synced_at=UNSYNCED_EPOCH,
    )
    logger.info("webhook_user_created_from_membership", user_id=user.id, clerk_id=clerk_id)
    return user


async def _sync_org_and_invalidate(data: dict, session: AsyncSession, user: User) -> None:
    """Align org_id with the payload and drop the user's cached auth data.

    Invalidates rather than populates: the event carries the new role, but
    writing it before the request commits could serve a value for a transaction
    that later rolls back. Dropping an entry can only cost a DB read.
    """
    org_id = _organization_id(data)
    if org_id and user.org_id != org_id:
        await user_repository.update_org_id(session, user, org_id)

    await user_cache.invalidate_user(clerk_id=user.clerk_id)


async def handle_membership_created(ctx: WebhookContext) -> None:
    """Attach a user to an organisation, creating the user row if needed."""
    data = ctx.data
    session = ctx.session
    user = await _resolve_or_create_user(data, session)
    if user is None:
        return

    await _sync_org_and_invalidate(data, session, user)
    await events.publish(USER_SYNCED, session=session, user_id=user.id, metadata=data.get("public_metadata") or {})
    logger.info(
        "webhook_membership_created",
        user_id=user.id,
        org_id=_organization_id(data),
        role=data.get("role"),
    )


async def handle_membership_updated(ctx: WebhookContext) -> None:
    """Apply a membership change — in practice, a role change."""
    data = ctx.data
    session = ctx.session
    public_user_data = data.get("public_user_data") or {}
    clerk_id = public_user_data.get("user_id")

    if not clerk_id:
        logger.warning("webhook_membership_missing_user_id", membership_id=data.get("id"))
        return

    user = await user_repository.get_by_clerk_id(session, clerk_id)
    if user is None:
        logger.warning("webhook_membership_updated_unknown", clerk_id=clerk_id)
        return

    await _sync_org_and_invalidate(data, session, user)
    logger.info("webhook_membership_updated", user_id=user.id, role=data.get("role"))


async def handle_membership_deleted(ctx: WebhookContext) -> None:
    """Revoke access when a user is removed from, or leaves, an organisation.

    Clears org_id and drops the cached role so revocation is immediate rather than bounded by
    the cache TTL.

    Guarded against a reversed created/deleted pair: moving a user from org A to
    org B emits created(B) and deleted(A) with no ordering guarantee, and acting
    on a late deleted(A) would clear org B. The org loss would self-heal via
    JIT, but comparing the event's org against the user's
    *current* org_id catches it — but only when both are present. A NULL
    user.org_id means created(B) never landed, so there is no "B" to have been
    reversed against and the event is a genuine offboarding.

    Publishes USER_OFFBOARDED.
    """
    data = ctx.data
    session = ctx.session
    public_user_data = data.get("public_user_data") or {}
    clerk_id = public_user_data.get("user_id")

    if not clerk_id:
        logger.warning("webhook_membership_missing_user_id", membership_id=data.get("id"))
        return

    user = await user_repository.get_by_clerk_id(session, clerk_id)
    if user is None:
        logger.info("webhook_membership_deleted_noop", clerk_id=clerk_id)
        return

    event_org_id = _organization_id(data)
    if event_org_id and user.org_id and event_org_id != user.org_id:
        logger.info(
            "webhook_membership_deleted_org_mismatch",
            user_id=user.id,
            event_org_id=event_org_id,
        )
        return

    user.org_id = None
    session.add(user)
    await session.flush()

    await events.publish(USER_OFFBOARDED, session=session, user_id=user.id)
    await user_cache.invalidate_user(clerk_id=user.clerk_id)


clerk_dispatcher = ClerkEventDispatcher()

clerk_dispatcher.register("user.created", handle_user_created)
clerk_dispatcher.register("user.updated", handle_user_updated)
clerk_dispatcher.register("user.deleted", handle_user_deleted)

# Clerk's dashboard webhook catalog names these in camelCase, while the
# application-log docs use snake_case. They are different taxonomies and the
# dashboard is what Svix actually registers — but a wrong key here fails
# SILENTLY: the handler simply never runs, with no error and no 4xx. Both
# spellings are registered so the subscription cannot miss.
for _prefix in ("organizationMembership", "organization_membership"):
    clerk_dispatcher.register(f"{_prefix}.created", handle_membership_created)
    clerk_dispatcher.register(f"{_prefix}.updated", handle_membership_updated)
    clerk_dispatcher.register(f"{_prefix}.deleted", handle_membership_deleted)
