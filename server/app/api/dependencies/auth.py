"""Authentication dependencies for FastAPI endpoints."""

from typing import Annotated

from fastapi import (
    Depends,
    Request,
)
from fastapi.security import OAuth2AuthorizationCodeBearer

from app.api.dependencies.database import DbSession
from app.core.config import settings
from app.core.logging import (
    bind_context,
    logger,
)
from app.exceptions.base import AuthenticationError
from app.models.user import User
from app.services.user import user_provider

oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=settings.auth.AUTHORIZE_URL,
    tokenUrl=settings.auth.TOKEN_URL,
    scopes={
        "openid": "OpenID Connect",
        "profile": "Profile information",
        "email": "Email address",
        "offline_access": "Refresh token",
    },
    auto_error=False,
)


def get_clerk_id(request: Request) -> str:
    """Extract clerk_id from request.state (set by AuthMiddleware).

    Args:
        request: The incoming request with auth data in state.

    Returns:
        The Clerk user ID string.

    Raises:
        AuthenticationError: If no clerk_id is present.
    """
    clerk_id = getattr(request.state, "clerk_id", None)
    if not clerk_id:
        logger.error("clerk_id_not_in_request_state")
        raise AuthenticationError("Authentication required")
    return clerk_id


async def get_current_user(
    request: Request,
    session: DbSession,
    clerk_id: str = Depends(get_clerk_id),
    _token: str = Depends(oauth2_scheme),
) -> User:
    """Get the current authenticated user with JIT provisioning.

    Looks up the user by clerk_id (cache -> DB -> Clerk API).
    Creates the user in the database on first access.

    Args:
        request: The incoming request
        session: Database session
        clerk_id: The Clerk user ID from middleware
        _token: OAuth2 token (used only for Swagger UI authorize button)

    Returns:
        The authenticated User object.

    Raises:
        AuthenticationError: If user cannot be provisioned.
    """
    try:
        user = await user_provider.get_or_create_user(clerk_id, session)

        # Store internal UUID in request state for logging and database context
        request.state.user_id = user.id

        # Rebind logging context with the internal UUID
        bind_context(user_id=user.id)

    except Exception as e:
        logger.error("user_provisioning_failed", clerk_id=clerk_id, error=str(e))
        raise AuthenticationError("Failed to provision user") from e

    return user


# Type alias for cleaner endpoint signatures
CurrentUser = Annotated[User, Depends(get_current_user)]
