"""User repository for database operations."""

from datetime import (
    UTC,
    datetime,
)
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.logging import logger
from app.models.user import User


class UserRepository:
    """Repository for user database operations."""

    @staticmethod
    async def get_by_id(session: AsyncSession, user_id: str) -> Optional[User]:
        """Get a user by internal ID.

        Args:
            session: Database session
            user_id: User ID (UUID string)

        Returns:
            User if found, None otherwise.
        """
        return await session.get(User, user_id)

    @staticmethod
    async def get_by_clerk_id(session: AsyncSession, clerk_id: str) -> Optional[User]:
        """Get a user by Clerk ID.

        Args:
            session: Database session
            clerk_id: Clerk user ID (e.g., "user_2abc123xyz")

        Returns:
            User if found, None otherwise.
        """
        statement = select(User).where(User.clerk_id == clerk_id)
        result = await session.execute(statement)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_email(session: AsyncSession, email: str) -> Optional[User]:
        """Get a user by email.

        Args:
            session: Database session
            email: User's email

        Returns:
            User if found, None otherwise.
        """
        statement = select(User).where(User.email == email)
        result = await session.execute(statement)
        return result.scalar_one_or_none()

    @staticmethod
    async def create(
        session: AsyncSession,
        clerk_id: str,
        email: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        avatar_url: Optional[str] = None,
        email_verified: bool = False,
    ) -> User:
        """Create a new user from Clerk data.

        Args:
            session: Database session
            clerk_id: Clerk user ID
            email: User's email address
            first_name: User's first name
            last_name: User's last name
            avatar_url: User's avatar URL
            email_verified: Whether the email is verified

        Returns:
            The created User.
        """
        user = User(
            clerk_id=clerk_id,
            email=email,
            first_name=first_name,
            last_name=last_name,
            avatar_url=avatar_url,
            email_verified=email_verified,
        )
        session.add(user)
        await session.flush()
        await session.refresh(user)

        logger.info("user_created", user_id=user.id, clerk_id=clerk_id, email=email)
        return user

    @staticmethod
    async def update_from_clerk(
        session: AsyncSession,
        user: User,
        email: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        avatar_url: Optional[str] = None,
        email_verified: Optional[bool] = None,
    ) -> User:
        """Update a user's profile from Clerk data.

        Args:
            session: Database session
            user: The user to update
            email: New email address
            first_name: New first name
            last_name: New last name
            avatar_url: New avatar URL
            email_verified: New email verification status

        Returns:
            The updated User.
        """
        now = datetime.now(UTC)
        if email is not None:
            user.email = email
        if first_name is not None:
            user.first_name = first_name
        if last_name is not None:
            user.last_name = last_name
        if avatar_url is not None:
            user.avatar_url = avatar_url
        if email_verified is not None:
            user.email_verified = email_verified
        user.updated_at = now
        user.last_synced_at = now

        session.add(user)
        await session.flush()
        await session.refresh(user)

        logger.info("user_updated", user_id=user.id, clerk_id=user.clerk_id)
        return user

    @staticmethod
    async def delete(session: AsyncSession, user_id: str) -> bool:
        """Delete a user by internal ID.

        Args:
            session: Database session
            user_id: User ID (UUID string)

        Returns:
            True if deleted, False if not found.
        """
        user = await session.get(User, user_id)
        if not user:
            return False

        await session.delete(user)
        logger.info("user_deleted", user_id=user_id)
        return True


user_repository = UserRepository()
