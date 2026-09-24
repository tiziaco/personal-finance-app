"""User service with JIT provisioning.

Caching lives in app/modules/account/cache.py — see UserCache.
"""

import asyncio
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.shared.memory.factory import delete_user_memory
from app.core.events import events
from app.core.logging import logger
from app.exceptions.base import AuthorizationError
from app.integrations.clerk import (
    ClerkUserNotFoundError,
    clerk_client,
)
from app.integrations.clerk.timestamps import clerk_timestamp_to_datetime
from app.modules.account.cache import user_cache
from app.modules.account.models import User
from app.modules.account.repository import user_repository
from app.utils.cache import MISS

# Published for the modules above account (architecture §5). A subscriber
# imports the constant, so a renamed event is an import error, not a silent
# no-op.
USER_SYNCED = "account.user_synced"  # session, user_id, metadata — after JIT provisioning or a Clerk create
USER_ERASING = "account.user_erasing"  # session, user_id — before the row is anonymised
USER_OFFBOARDED = "account.user_offboarded"  # session, user_id — the user left their organisation


def merge_clerk_metadata(clerk_user: Any) -> dict:
    """Flatten a Clerk user's public metadata, top level winning over memberships.

    Invitation metadata may be stamped on the user or on the organisation
    membership, depending on how the invite was issued. Callers should not
    have to know which, so this collapses both into one dict with top-level
    values taking precedence.

    Args:
        clerk_user: A Clerk SDK user object.

    Returns:
        A merged metadata dict; empty if the object carries none.
    """
    merged: dict = {}

    top_level = getattr(clerk_user, "public_metadata", None) or {}
    if isinstance(top_level, dict):
        merged.update(top_level)

    for membership in getattr(clerk_user, "organization_memberships", None) or []:
        membership_md = getattr(membership, "public_metadata", None) or {}
        if not isinstance(membership_md, dict):
            continue
        for key in ("supplier_id", "replace"):
            if not merged.get(key) and membership_md.get(key):
                merged[key] = membership_md[key]

    return merged


class UserService:
    """Provides user objects with JIT provisioning.

    Flow: DB (indexed clerk_id lookup) -> Clerk API (JIT create)
    """

    async def resolve_user(
        self,
        clerk_id: str,
        org_id: str,
        session: AsyncSession,
    ) -> User:
        """Resolve the current user by clerk_id, JIT-provisioning if needed.

        Updates org_id on every call so the DB stays in sync if the user's org
        changes (e.g. admin re-assigns to a different organisation).

        Args:
            clerk_id: The Clerk user ID.
            org_id: The Clerk organisation ID from the JWT.
            session: Database session for DB operations.

        Returns:
            The User object (attached to the current session).

        Raises:
            RuntimeError: If user cannot be provisioned from Clerk.
            UserAlreadyExistsError: A genuine (non-race) unique constraint
                conflict during provisioning — see UserRepository.create_or_get.
        """
        # 1. Look up by clerk_id (unique + indexed -> single index scan).
        #    There is deliberately no clerk_id -> user_id cache: a hit would
        #    still cost one indexed lookup, and FastAPI's per-request Depends
        #    cache already prevents repeat resolution within a request.
        user = await user_repository.get_by_clerk_id(session, clerk_id)
        if user:
            # Keep org_id in sync — but only when the JWT carries a real org context
            if org_id and user.org_id != org_id:
                user = await user_repository.update_org_id(session, user, org_id)
            return user

        # 2. JIT: Fetch from Clerk and create in DB
        logger.info("jit_provisioning_user", clerk_id=clerk_id)

        try:
            clerk_user = await asyncio.to_thread(clerk_client.get_user, clerk_id)
        except ClerkUserNotFoundError:
            logger.error("clerk_user_not_found_during_provisioning", clerk_id=clerk_id)
            raise

        email = clerk_client.get_primary_email(clerk_user)

        if not email:
            logger.error("clerk_user_missing_email", clerk_id=clerk_id)
            raise RuntimeError(f"No email found for Clerk user {clerk_id}")

        # JWT had no org context (e.g. OIDC token) — look up the user's org from Clerk
        if not org_id:
            membership = await asyncio.to_thread(clerk_client.get_first_org_membership, clerk_id)
            if not membership:
                logger.warning("jit_provisioning_no_org_membership", clerk_id=clerk_id)
                raise AuthorizationError("Organization membership required")
            org_id, jit_role = membership
            await user_cache.set_org_role(clerk_id, jit_role)  # warm for auth fallback
            logger.info("jit_org_resolved_from_clerk", clerk_id=clerk_id, org_id=org_id)

        user = await user_repository.create_or_get(
            session=session,
            clerk_id=clerk_id,
            email=email,
            org_id=org_id,
            first_name=clerk_user.first_name,
            last_name=clerk_user.last_name,
            avatar_url=clerk_user.image_url,
            email_verified=bool(clerk_user.primary_email_address_id),
            last_synced_at=clerk_timestamp_to_datetime(getattr(clerk_user, "updated_at", None)),
        )

        await events.publish(USER_SYNCED, session=session, user_id=user.id, metadata=merge_clerk_metadata(clerk_user))

        return user

    async def resolve_org_role(self, clerk_id: str) -> Optional[str]:
        """Resolve org role from cache, falling back to Clerk API.

        Used by get_current_role() when the JWT carries no org context.

        Cached for UserCache.role_ttl seconds (default 60) — deliberately
        shorter than the supplier TTL, because this value feeds require_role(),
        so a demoted or revoked role stays honoured for at most that long.

        Revocation is now immediate in the common case: the
        organization_membership.updated and .deleted webhooks invalidate this
        entry. The TTL remains the bound for a dropped or delayed event.
        """
        cached = await user_cache.get_org_role(clerk_id)
        if cached is not MISS:
            return cached
        membership = await asyncio.to_thread(clerk_client.get_first_org_membership, clerk_id)
        if membership:
            _, role = membership
            await user_cache.set_org_role(clerk_id, role)
            return role
        return None

    async def erase_user(
        self,
        user: User,
        session: AsyncSession,
    ) -> None:
        """Run the GDPR erasure cascade for one user.

        Shared by DELETE /api/v1/auth/me and the user.deleted webhook. The
        caller is responsible for deleting the user from Clerk — the webhook
        path must not, because a Clerk-side deletion is what produced the
        event.

        Step order is contractual. Subscribers to USER_ERASING and the memory
        deletion run before `anonymize_user()`, because they are keyed by
        identifiers it destroys. The org-role cache is invalidated last, under
        the clerk_id captured before anonymisation rewrote it. Its position
        against the commit does not matter: it is refilled from Clerk, not
        from this table, and Clerk has already deleted the user.

        Not committed here: the caller's DbSession commits before the response
        is sent. delete_user_memory is irreversible, so anything a caller runs
        after this call that fails before the commit would roll back the
        anonymisation with the memories already gone. Neither caller runs
        anything after it today.

        Idempotent: on a second run the conversation list is empty, mem0
        deletion is a no-op, and the row is already anonymised.

        Args:
            user: The user to erase. Must be attached to `session`.
            session: Database session. Committed by the caller's DbSession.
        """
        original_clerk_id = user.clerk_id

        # Inline subscribers run here, in this transaction, before the row is
        # anonymised — conversation soft-delete, checkpoints, names, and the
        # supplier link. Their identifiers are what anonymize_user() destroys.
        subscriber_count = await events.publish(USER_ERASING, session=session, user_id=user.id)
        if subscriber_count == 0:
            # Never raise here — erasure must proceed either way — but a
            # script, a worker, or a fork that dropped a subscriber leaves the
            # cascade silently doing nothing, and only a loud log catches it.
            logger.error("user_erasing_had_no_subscribers", user_id=user.id)

        await delete_user_memory(user.id)

        user.anonymize_user()
        session.add(user)

        await user_cache.invalidate_user(clerk_id=original_clerk_id)

        logger.info("user_erased", user_id=user.id, subscriber_count=subscriber_count)

    async def exists_in_clerk(self, clerk_id: str) -> bool:
        """Report whether Clerk still holds this user.

        Thin wrapper so callers outside the user service do not import
        clerk_client directly (CLAUDE.md auth rule).

        The webhook create paths gate on this. A webhook payload is a
        past-tense statement and svix redelivers with backoff, so a snapshot
        taken before a deletion can land after it; Clerk is the only thing
        that can still tell the two apart once erase_user() has rewritten
        clerk_id. JIT provisioning already asks the same question implicitly,
        by holding a live JWT.

        Only the 404 is an answer. Every other Clerk error is inconclusive
        and propagates, so the delivery fails and svix retries rather than a
        row being created — or declined — on a maybe.

        Args:
            clerk_id: The Clerk user identifier.

        Returns:
            True if Clerk still holds the user, False on a 404.

        Raises:
            ClerkAuthenticationError / ClerkRateLimitError / ClerkAPIError:
                Propagated from ClerkClient.get_user.
        """
        try:
            await asyncio.to_thread(clerk_client.get_user, clerk_id)
            return True
        except ClerkUserNotFoundError:
            return False

    async def delete_user_from_clerk(self, clerk_id: str) -> None:
        """Delete a user from Clerk by clerk_id.

        Thin wrapper so callers outside the user service do not import
        clerk_client directly (CLAUDE.md auth rule).

        Args:
            clerk_id: The Clerk user identifier.

        Raises:
            ClerkAPIError / ClerkAuthenticationError: Propagated from ClerkClient.delete_user.
        """
        await asyncio.to_thread(clerk_client.delete_user, clerk_id)


user_service = UserService()
