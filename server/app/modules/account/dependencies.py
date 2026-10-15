"""Account dependencies — who is calling.

The user is the tenant: there is no organisation and no role. Resource
ownership ("does this user own this conversation?") is checked in the owning
module's dependencies; nothing here touches a table but the user row.
"""

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import OAuth2AuthorizationCodeBearer

from app.core.config import settings
from app.core.logging import bind_context, logger
from app.database.dependencies import DbSession
from app.exceptions.base import AuthenticationError
from app.modules.account.exceptions import UserProvisioningError
from app.modules.account.models import User
from app.modules.account.service import user_service

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
    """Extract clerk_id from request.state (set by AuthMiddleware)."""
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
    """Get the current authenticated user with JIT provisioning."""
    try:
        user = await user_service.resolve_user(session, clerk_id)
        request.state.user_id = user.id
        bind_context(user_id=user.id)
    except Exception as e:
        logger.error("user_provisioning_failed", clerk_id=clerk_id, error=str(e))
        raise UserProvisioningError("Failed to provision user") from e
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
