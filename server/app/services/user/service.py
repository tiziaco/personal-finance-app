"""User service with JIT provisioning.

Caching lives in app/services/user/cache.py — see UserCache.
"""

import asyncio
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.base import AuthorizationError
from app.models.user import User
from app.services.clerk import (
    ClerkUserNotFoundError,
    clerk_service,
)
from app.services.user.cache import (
    _MISS,
    user_cache,
)
from app.services.user.repository import user_repository
from app.services.user.supplier_repository import supplier_repository

from app.core.logging import logger


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
            clerk_user = await asyncio.to_thread(clerk_service.get_user, clerk_id)
        except ClerkUserNotFoundError:
            logger.error("clerk_user_not_found_during_provisioning", clerk_id=clerk_id)
            raise

        email = clerk_service.get_primary_email(clerk_user)

        if not email:
            logger.error("clerk_user_missing_email", clerk_id=clerk_id)
            raise RuntimeError(f"No email found for Clerk user {clerk_id}")

        # JWT had no org context (e.g. OIDC token) — look up the user's org from Clerk
        if not org_id:
            membership = await asyncio.to_thread(clerk_service.get_first_org_membership, clerk_id)
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
        )

        # Supplier-linking on JIT creation: read public_metadata.supplier_id,
        # falling back to org membership metadata if not set at the user level.
        supplier_id_from_invitation: Optional[str] = None
        top_level_md = getattr(clerk_user, "public_metadata", None) or {}
        if isinstance(top_level_md, dict):
            supplier_id_from_invitation = top_level_md.get("supplier_id")
        if not supplier_id_from_invitation:
            memberships = getattr(clerk_user, "organization_memberships", None) or []
            for membership in memberships:
                md = getattr(membership, "public_metadata", None) or {}
                if isinstance(md, dict) and md.get("supplier_id"):
                    supplier_id_from_invitation = md["supplier_id"]
                    break

        # When public_metadata.replace is truthy, the JIT linker may overwrite
        # an existing contact_id. Without it, only an unlinked supplier
        # (contact_id is None) gets linked, so a normal first invite is unaffected.
        replace_flag: bool = False
        if isinstance(top_level_md, dict) and top_level_md.get("replace"):
            replace_flag = True
        if not replace_flag:
            memberships = getattr(clerk_user, "organization_memberships", None) or []
            for membership in memberships:
                md = getattr(membership, "public_metadata", None) or {}
                if isinstance(md, dict) and md.get("replace"):
                    replace_flag = True
                    break

        if supplier_id_from_invitation:
            supplier = await supplier_repository.get_by_id(session, supplier_id_from_invitation)
            if supplier is not None and (
                supplier.contact_id is None or replace_flag
            ):
                # Capture BEFORE overwriting. With replace_flag this is a
                # RE-LINK: the displaced contact holds a cached
                # user_id -> supplier_id entry that is now wrong, and once the
                # old id is gone that entry is unreachable for invalidation.
                previous_contact_id = supplier.contact_id
                supplier = await supplier_repository.set_contact_id(session, supplier, user.id)

                # Invalidate both sides of the re-link. Safe before commit:
                # dropping an entry can only cost a DB read, never serve a
                # wrong value (populating before commit would not be safe).
                if previous_contact_id and previous_contact_id != user.id:
                    await user_cache.invalidate_user(user_id=previous_contact_id)
                # Not dead on the pure-JIT path: create_or_get's race branch
                # can return an EXISTING user that falls through to here, and
                # that user may hold a cached None from an earlier 403.
                await user_cache.invalidate_user(user_id=user.id)

                logger.info(
                    "supplier_linked_on_jit",
                    supplier_id=supplier.id,
                    user_id=user.id,
                    previous_contact_id=previous_contact_id,
                    replace=replace_flag,
                )

        return user

    async def resolve_org_role(self, clerk_id: str) -> Optional[str]:
        """Resolve org role from cache, falling back to Clerk API.

        Used by get_current_role() when the JWT carries no org context.

        Cached for UserCache.role_ttl seconds (default 60) — deliberately
        shorter than the supplier TTL, because this value feeds require_role(),
        so a demoted or revoked role stays honoured for at most that long.

        TODO(follow-up): a Clerk organizationMembership.updated/deleted webhook
        calling user_cache.invalidate_user(clerk_id=...) would make revocation
        immediate. Out of scope for now: no webhook infrastructure exists (no
        svix dependency, no route, no raw-body middleware).
        """
        cached = await user_cache.get_org_role(clerk_id)
        if cached is not _MISS:
            return cached
        membership = await asyncio.to_thread(clerk_service.get_first_org_membership, clerk_id)
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

    async def delete_user_from_clerk(self, clerk_id: str) -> None:
        """Delete a user from Clerk by clerk_id.

        Thin wrapper so callers outside the user service do not import
        clerk_service directly (CLAUDE.md auth rule).

        Args:
            clerk_id: The Clerk user identifier.

        Raises:
            ClerkAPIError / ClerkAuthenticationError: Propagated from ClerkService.delete_user.
        """
        await asyncio.to_thread(clerk_service.delete_user, clerk_id)


user_service = UserService()
