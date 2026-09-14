"""Handlers for Clerk organization_membership.* webhook events.

These close the role-revocation gap: without them a revoked role stays
honoured for up to UserCache.role_ttl seconds.

There is deliberately no ordering guard built on the membership payload's own
timestamp, and no membership sync column: reusing User.last_synced_at would
conflate two unrelated clocks, and a fresh user.updated would start dropping
older-but-valid membership events. The one place this module touches
last_synced_at is the opposite move — seeding UNSYNCED_EPOCH on a row created
from a membership event, so a *real* user.* event is never mistaken for stale.

`handle_membership_deleted` guards one specific reversal; every other
reordering is left unguarded and self-heals, because JIT re-syncs org_id from
the JWT on the user's next request.
"""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.integrations.clerk.timestamps import UNSYNCED_EPOCH
from app.integrations.clerk.webhooks.schemas import WebhookContext
from app.models.user import User
from app.services.user import (
    user_cache,
    user_repository,
    user_service,
)


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

    await user_cache.invalidate_user(clerk_id=user.clerk_id, user_id=user.id)


async def handle_membership_created(ctx: WebhookContext) -> None:
    """Attach a user to an organisation, creating the user row if needed."""
    data = ctx.data
    session = ctx.session
    user = await _resolve_or_create_user(data, session)
    if user is None:
        return

    await _sync_org_and_invalidate(data, session, user)
    await user_service.link_supplier_from_metadata(user, data.get("public_metadata") or {}, session)
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

    Clears org_id, unlinks any supplier this user was the contact for, and
    drops the cached role so revocation is immediate rather than bounded by
    the cache TTL.

    Guarded against a reversed created/deleted pair: moving a user from org A to
    org B emits created(B) and deleted(A) with no ordering guarantee, and acting
    on a late deleted(A) would clear org B and unlink the supplier. The org loss
    would self-heal via JIT, but JIT does not restore Supplier.contact_id, so a
    wrong unlink is permanent. Comparing the event's org against the user's
    *current* org_id catches it — but only when both are present. A NULL
    user.org_id means created(B) never landed, so there is no "B" to have been
    reversed against and the event is a genuine offboarding.

    Unlinking leaves the supplier contact-less with no signal to a project
    manager beyond this log line — a known cost, recorded in the design spec.
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

    supplier_id = await user_service.unlink_supplier_contact(user.id, session)
    await user_cache.invalidate_user(clerk_id=user.clerk_id, user_id=user.id)

    if supplier_id is not None:
        logger.info(
            "supplier_unlinked_on_offboarding",
            user_id=user.id,
            supplier_id=supplier_id,
            org_id=event_org_id,
        )
