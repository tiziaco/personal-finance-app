"""User service with JIT provisioning.

Caching lives in app/services/user/cache.py — see UserCache.
"""

import asyncio
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.shared.checkpointing import delete_conversation_checkpoints
from app.agents.shared.memory.factory import delete_user_memory
from app.core.logging import logger
from app.exceptions.base import AuthorizationError
from app.integrations.clerk import (
    ClerkUserNotFoundError,
    clerk_client,
)
from app.integrations.clerk.timestamps import clerk_timestamp_to_datetime
from app.models.user import User
from app.services.conversation import conversation_service
from app.services.user.cache import (
    _MISS,
    user_cache,
)
from app.services.user.repository import user_repository
from app.services.user.supplier_repository import supplier_repository


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

        await self.link_supplier_from_metadata(user, merge_clerk_metadata(clerk_user), session)

        return user

    async def link_supplier_from_metadata(
        self,
        user: User,
        metadata: dict,
        session: AsyncSession,
    ) -> Optional[str]:
        """Link a supplier to this user based on invitation metadata.

        Called from JIT provisioning and from two webhook handlers, so it must
        be safely repeatable. Only an unlinked supplier is claimed, unless the
        metadata carries a truthy `replace` flag — so a retried event, or a
        second invite for an already-linked supplier, changes nothing.

        Cache invalidation is safe before the caller's commit: dropping an
        entry can only cost a DB read, never serve a wrong value.

        Args:
            user: The user to link.
            metadata: Merged public metadata; read for `supplier_id` and `replace`.
            session: DB session. Flushed, not committed.

        Returns:
            The linked Supplier.id, or None if nothing was linked.
        """
        supplier_id = metadata.get("supplier_id")
        if not supplier_id:
            return None

        replace_flag = bool(metadata.get("replace"))

        supplier = await supplier_repository.get_by_id(session, supplier_id)
        if supplier is None:
            logger.warning("supplier_link_target_missing", supplier_id=supplier_id, user_id=user.id)
            return None
        if supplier.contact_id is not None and not replace_flag:
            return None

        # Capture BEFORE overwriting. With replace_flag this is a RE-LINK: the
        # displaced contact holds a cached user_id -> supplier_id entry that is
        # now wrong, and once the old id is gone that entry is unreachable.
        previous_contact_id = supplier.contact_id
        supplier = await supplier_repository.set_contact_id(session, supplier, user.id)

        if previous_contact_id and previous_contact_id != user.id:
            await user_cache.invalidate_user(user_id=previous_contact_id)
        await user_cache.invalidate_user(user_id=user.id)

        logger.info(
            "supplier_linked",
            supplier_id=supplier.id,
            user_id=user.id,
            previous_contact_id=previous_contact_id,
            replace=replace_flag,
        )
        return supplier.id

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
        if cached is not _MISS:
            return cached
        membership = await asyncio.to_thread(clerk_client.get_first_org_membership, clerk_id)
        if membership:
            _, role = membership
            await user_cache.set_org_role(clerk_id, role)
            return role
        return None

    async def get_supplier_id_for_user(
        self,
        user_id: str,
        session: AsyncSession,
    ) -> Optional[str]:
        """Resolve the Supplier.id linked to this user via Supplier.contact_id.

        Cached per-user for UserCache.ttl seconds (default 300). A cached None
        is honoured as "known not linked" rather than treated as a miss.
        Returns None if no (non-soft-deleted) supplier is linked.

        Args:
            user_id: Local User.id.
            session: DB session.

        Returns:
            The Supplier.id, or None if no link exists.
        """
        cached = await user_cache.get_supplier_id(user_id)
        if cached is not _MISS:
            return cached

        supplier_id = await supplier_repository.get_id_by_contact_id(session, user_id)

        await user_cache.set_supplier_id(user_id, supplier_id)
        return supplier_id

    async def unlink_supplier_contact(
        self,
        user_id: str,
        session: AsyncSession,
    ) -> Optional[str]:
        """Clear Supplier.contact_id for any supplier this user manages.

        Used by GDPR erasure. Anonymising the User row leaves Supplier.contact_id
        pointing at it, which still records *which supplier this person managed* —
        a link back to the individual that survives anonymisation of the row
        itself. Clearing it removes that association.

        The supplier is left contact-less until someone is re-invited to it.

        Args:
            user_id: Local User.id.
            session: DB session. Flushed, not committed — the caller commits.

        Returns:
            The unlinked Supplier.id, or None if the user managed no supplier.
        """
        supplier = await supplier_repository.get_by_contact_id(session, user_id)
        if supplier is None:
            return None

        supplier = await supplier_repository.set_contact_id(session, supplier, None)
        await user_cache.invalidate_user(user_id=user_id)
        logger.info("supplier_unlinked_on_erasure", supplier_id=supplier.id, user_id=user_id)
        return supplier.id

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

        Step order is contractual. Checkpoints and memories are keyed by
        identifiers that anonymize_user() destroys, so they must be cleared
        first. Cache invalidation happens after the commit, using the
        clerk_id captured before anonymisation rewrote it.

        Idempotent: on a second run the conversation list is empty, mem0
        deletion is a no-op, and the row is already anonymised.

        Args:
            user: The user to erase. Must be attached to `session`.
            session: Database session. Committed by this method.
        """
        original_clerk_id = user.clerk_id

        conversation_ids = await conversation_service.soft_delete_all_user_conversations(session, user.id)
        for conv_id in conversation_ids:
            await delete_conversation_checkpoints(conv_id)

        await delete_user_memory(user.id)
        await self.unlink_supplier_contact(user.id, session)

        # Eagerly load conversations so anonymize_user() can iterate them
        # without a synchronous lazy load on an async session (MissingGreenlet).
        await session.refresh(user, attribute_names=["conversations"])
        user.anonymize_user()
        session.add(user)
        await session.commit()

        await user_cache.invalidate_user(clerk_id=original_clerk_id, user_id=user.id)

        logger.info(
            "user_erased",
            user_id=user.id,
            conversation_count=len(conversation_ids),
        )

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
