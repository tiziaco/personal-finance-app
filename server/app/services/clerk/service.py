"""Clerk API service for fetching user data."""

from typing import Optional

from clerk_backend_api import (
    Clerk,
    ClerkErrors,
)

from app.core.config import settings
from app.core.logging import logger
from app.services.clerk.exceptions import (
    ClerkAPIError,
    ClerkAuthenticationError,
    ClerkRateLimitError,
    ClerkUserNotFoundError,
)


class ClerkService:
    """Service for interacting with the Clerk Backend API."""

    def __init__(self):
        self._client: Optional[Clerk] = None

    @property
    def client(self) -> Clerk:
        """Lazy-initialize the Clerk client."""
        if self._client is None:
            self._client = Clerk(bearer_auth=settings.auth.SECRET_KEY.get_secret_value())
        return self._client

    def get_user(self, clerk_id: str):
        """Fetch a user from Clerk by their clerk_id.

        Args:
            clerk_id: The Clerk user ID (e.g., "user_2abc123xyz").

        Returns:
            The Clerk user object.

        Raises:
            ClerkUserNotFoundError: If user not found in Clerk.
            ClerkAuthenticationError: If authentication with Clerk API fails.
            ClerkRateLimitError: If Clerk API rate limit is exceeded.
            ClerkAPIError: If any other Clerk API error occurs.
        """
        try:
            user = self.client.users.get(user_id=clerk_id)
            logger.debug("clerk_user_fetched", clerk_id=clerk_id)
            return user

        except ClerkErrors as e:
            # Check for specific error types based on HTTP status code
            status_code = e.raw_response.status_code if hasattr(e, "raw_response") else None

            if status_code == 404:
                logger.warning("clerk_user_not_found", clerk_id=clerk_id)
                raise ClerkUserNotFoundError(
                    f"User {clerk_id} not found in Clerk",
                    clerk_id=clerk_id,
                ) from e
            elif status_code == 401:
                logger.error("clerk_authentication_failed", clerk_id=clerk_id)
                raise ClerkAuthenticationError(
                    "Authentication with Clerk API failed",
                    clerk_id=clerk_id,
                ) from e
            elif status_code == 429:
                logger.warning("clerk_rate_limit_exceeded", clerk_id=clerk_id)
                raise ClerkRateLimitError(
                    "Clerk API rate limit exceeded",
                    clerk_id=clerk_id,
                ) from e

            # Generic API error for other cases
            logger.error("clerk_api_error", clerk_id=clerk_id, status_code=status_code, error=str(e))
            raise ClerkAPIError(
                f"Clerk API error: {str(e)}",
                clerk_id=clerk_id,
            ) from e

        except Exception as e:
            logger.exception("clerk_unexpected_error", clerk_id=clerk_id, error=str(e))
            raise ClerkAPIError(
                f"Unexpected error fetching user from Clerk: {str(e)}",
                clerk_id=clerk_id,
            ) from e

    def delete_user(self, clerk_id: str) -> None:
        """Delete a user from Clerk.

        Args:
            clerk_id: The Clerk user ID to delete.

        Raises:
            ClerkAuthenticationError: If authentication with Clerk API fails.
            ClerkAPIError: If any other Clerk API error occurs.
        """
        try:
            self.client.users.delete(user_id=clerk_id)
            logger.info("clerk_user_deleted", clerk_id=clerk_id)

        except ClerkErrors as e:
            status_code = e.raw_response.status_code if hasattr(e, "raw_response") else None

            if status_code == 404:
                logger.warning("clerk_user_not_found_on_delete", clerk_id=clerk_id)
                return  # Already gone — not an error
            elif status_code == 401:
                logger.error("clerk_authentication_failed_on_delete", clerk_id=clerk_id)
                raise ClerkAuthenticationError(
                    "Authentication with Clerk API failed",
                    clerk_id=clerk_id,
                ) from e

            logger.error("clerk_api_error_on_delete", clerk_id=clerk_id, status_code=status_code, error=str(e))
            raise ClerkAPIError(
                f"Clerk API error: {str(e)}",
                clerk_id=clerk_id,
            ) from e

        except Exception as e:
            logger.exception("clerk_unexpected_error_on_delete", clerk_id=clerk_id, error=str(e))
            raise ClerkAPIError(
                f"Unexpected error deleting user from Clerk: {str(e)}",
                clerk_id=clerk_id,
            ) from e

    def get_primary_email(self, clerk_user) -> Optional[str]:
        """Extract the primary email address from a Clerk user.

        Args:
            clerk_user: The Clerk user object.

        Returns:
            The primary email address, or None if not found.
        """
        if not clerk_user.email_addresses:
            logger.warning("clerk_user_no_emails", clerk_id=getattr(clerk_user, "id", None))
            return None

        for email in clerk_user.email_addresses:
            if email.id == clerk_user.primary_email_address_id:
                return email.email_address

        # Fallback to first email if primary not found
        fallback_email = clerk_user.email_addresses[0].email_address
        logger.debug(
            "clerk_using_fallback_email",
            clerk_id=getattr(clerk_user, "id", None),
            email=fallback_email,
        )
        return fallback_email


clerk_service = ClerkService()
