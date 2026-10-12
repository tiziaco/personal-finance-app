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
`updated_at` against `User.last_synced_at` and drop the stale one.
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
from app.modules.account.models import User
from app.modules.account.repository import user_repository
from app.modules.account.service import USER_SYNCED, user_service

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

    Sign-up is public and every Clerk user is a customer, so the row is
    created unconditionally — the same row JIT provisioning would create at
    the user's first request.

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


clerk_dispatcher = ClerkEventDispatcher()

clerk_dispatcher.register("user.created", handle_user_created)
clerk_dispatcher.register("user.updated", handle_user_updated)
clerk_dispatcher.register("user.deleted", handle_user_deleted)
