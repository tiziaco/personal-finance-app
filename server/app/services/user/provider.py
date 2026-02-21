"""User provider with JIT provisioning and in-memory caching."""

import asyncio
from datetime import (
    UTC,
    datetime,
    timedelta,
)
from typing import (
    Dict,
    Optional,
    Tuple,
)

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models.user import User
from app.services.clerk import (
    ClerkUserNotFoundError,
    clerk_service,
)
from app.services.user.service import user_repository

# In-memory cache: clerk_id -> (user_id, cached_at)
# We cache only the internal user_id (not ORM objects) to avoid detached session issues.
_clerk_id_cache: Dict[str, Tuple[str, datetime]] = {}
CACHE_TTL = timedelta(minutes=5)


class UserProvider:
    """Provides user objects with JIT provisioning and caching.

    Flow: cache (clerk_id→user_id) -> DB -> Clerk API (create user)
    """

    async def get_or_create_user(self, clerk_id: str, session: AsyncSession) -> User:
        """Get a user by clerk_id, creating them via JIT provisioning if needed.

        Args:
            clerk_id: The Clerk user ID.
            session: Database session for DB operations.

        Returns:
            The User object (attached to the current session).

        Raises:
            RuntimeError: If user cannot be provisioned from Clerk.
        """
        # 1. Check cache for clerk_id -> user_id mapping
        if cached_user_id := self._get_from_cache(clerk_id):
            user = await user_repository.get_by_id(session, cached_user_id)
            if user:
                return user
            # Cache stale — user deleted from DB, clear and continue
            self.invalidate_cache(clerk_id)

        # 2. Check DB by clerk_id
        user = await user_repository.get_by_clerk_id(session, clerk_id)
        if user:
            self._set_cache(clerk_id, user.id)
            return user

        # 3. JIT: Fetch from Clerk and create in DB
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

        try:
            user = await user_repository.create(
                session=session,
                clerk_id=clerk_id,
                email=email,
                first_name=clerk_user.first_name,
                last_name=clerk_user.last_name,
                avatar_url=clerk_user.image_url,
                email_verified=bool(clerk_user.primary_email_address_id),
            )
        except IntegrityError:
            # Race condition: another request created this user concurrently
            await session.rollback()
            logger.info("jit_provisioning_race_resolved", clerk_id=clerk_id)
            user = await user_repository.get_by_clerk_id(session, clerk_id)
            if not user:
                raise RuntimeError(f"Failed to provision user {clerk_id}")

        self._set_cache(clerk_id, user.id)
        return user

    def _get_from_cache(self, clerk_id: str) -> Optional[str]:
        """Get a user_id from the in-memory cache if not expired."""
        entry = _clerk_id_cache.get(clerk_id)
        if entry is None:
            return None
        user_id, cached_at = entry
        if datetime.now(UTC) - cached_at < CACHE_TTL:
            logger.debug("user_cache_hit", clerk_id=clerk_id)
            return user_id
        _clerk_id_cache.pop(clerk_id, None)
        return None

    def _set_cache(self, clerk_id: str, user_id: str) -> None:
        """Store a clerk_id -> user_id mapping in the in-memory cache."""
        _clerk_id_cache[clerk_id] = (user_id, datetime.now(UTC))

    @staticmethod
    def invalidate_cache(clerk_id: str) -> None:
        """Remove a clerk_id from the cache."""
        _clerk_id_cache.pop(clerk_id, None)

    @staticmethod
    def clear_cache() -> None:
        """Clear the entire user cache."""
        _clerk_id_cache.clear()


user_provider = UserProvider()
