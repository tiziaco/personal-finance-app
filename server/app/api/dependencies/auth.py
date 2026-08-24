"""Authentication dependencies for FastAPI endpoints."""

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import OAuth2AuthorizationCodeBearer

from app.api.dependencies.database import DbSession
from app.core.config import settings
from app.core.logging import bind_context, logger
from app.exceptions.base import AuthenticationError, AuthorizationError
from app.models.enums import Role
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
        org_id = getattr(request.state, "org_id", None)
        user = await user_provider.get_or_create_user(clerk_id, org_id, session)
        request.state.user_id = user.id
        bind_context(user_id=user.id)
    except Exception as e:
        logger.error("user_provisioning_failed", clerk_id=clerk_id, error=str(e))
        raise AuthenticationError("Failed to provision user") from e
    return user


def get_current_role(request: Request) -> Role:
    """Extract the org role from request.state (set by AuthMiddleware).

    This is the backend portability seam. When migrating to WorkOS or a
    DB-backed role table, only this function changes — all endpoints and
    require_role() calls remain unchanged.

    Raises:
        AuthorizationError: If no org role is present or the role is unrecognised.
    """
    raw = getattr(request.state, "org_role", None)
    if not raw:
        raise AuthorizationError("No organization role in token")
    try:
        return Role(raw)
    except ValueError:
        raise AuthorizationError(f"Unknown role: {raw}")


def require_role(*allowed: Role):
    """Dependency factory that enforces one of the allowed roles.

    Usage:
        @router.get("/projects", dependencies=[InternalUserRole])
        async def list_projects(user: CurrentUser, ...): ...

    Args:
        *allowed: One or more Role values that are permitted.

    Returns:
        A FastAPI Depends object suitable for use in the dependencies list.
    """
    def dependency(role: Role = Depends(get_current_role)) -> None:
        if role not in allowed:
            raise AuthorizationError(
                f"Role '{role}' is not permitted. Required: {[r.value for r in allowed]}"
            )
    return Depends(dependency)


# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

# Authenticated user — use in endpoint signatures
CurrentUser = Annotated[User, Depends(get_current_user)]

# Current role — use when you need the role value in endpoint logic
CurrentRole = Annotated[Role, Depends(get_current_role)]

# ---------------------------------------------------------------------------
# Role guards — use in endpoint `dependencies=[...]` list
# ---------------------------------------------------------------------------

# Any internal user (not a supplier)
InternalUserRole = require_role(Role.PROJECT_MANAGER, Role.REVIEWER, Role.APPROVER)

# Project managers only
PMOnly = require_role(Role.PROJECT_MANAGER)

# Reviewers and project managers (can review documents)
ReviewerRole = require_role(Role.PROJECT_MANAGER, Role.REVIEWER)

# Suppliers only
SupplierRole = require_role(Role.SUPPLIER)
