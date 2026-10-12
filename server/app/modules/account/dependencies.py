"""Account dependencies — who is calling, with what role, in which organisation.

Resource-ownership checks ("does this user own this conversation?") live in the
owning module's service; nothing here touches a table but the user row.
"""

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import OAuth2AuthorizationCodeBearer

from app.core.config import settings
from app.core.logging import bind_context, logger
from app.database.dependencies import DbSession
from app.exceptions.base import AuthenticationError, AuthorizationError
from app.modules.account.models import Role, User
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
        org_id = getattr(request.state, "org_id", None)
        user = await user_service.resolve_user(session, clerk_id, org_id)
        request.state.user_id = user.id
        bind_context(user_id=user.id)
    except Exception as e:
        logger.error("user_provisioning_failed", clerk_id=clerk_id, error=str(e))
        raise AuthenticationError("Failed to provision user") from e
    return user


async def get_current_role(
    request: Request,
    _token: str = Depends(oauth2_scheme),
) -> Role:
    """Extract the org role from request.state, with Clerk API fallback.

    For JWTs with no org context (e.g. OIDC tokens), resolves the role from
    Clerk's org membership API (cached via UserService).

    This is the backend portability seam. When migrating to WorkOS or a
    DB-backed role table, only this function changes — all endpoints and
    require_role() calls remain unchanged.

    Raises:
        AuthorizationError: If no org role is present or the role is unrecognised.
    """
    raw = getattr(request.state, "org_role", None)

    if not raw:
        clerk_id = getattr(request.state, "clerk_id", None)
        if clerk_id:
            raw = await user_service.resolve_org_role(clerk_id)
            if raw:
                request.state.org_role = raw  # keep state consistent

    if not raw:
        raise AuthorizationError("No organization role in token")

    try:
        return Role(raw)
    except ValueError:
        raise AuthorizationError(f"Unknown role: {raw}")


CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentRole = Annotated[Role, Depends(get_current_role)]


def get_current_org_id(user: CurrentUser) -> str:
    """The caller's organisation, read from the resolved user row.

    The row, not `request.state.org_id`: JIT provisioning fills the org from
    Clerk when the token carries none, so the row is authoritative once
    `get_current_user` has run (architecture §9).

    Raises:
        AuthorizationError: If the user belongs to no organisation.
    """
    if user.org_id is None:
        raise AuthorizationError("Organization membership required")
    return user.org_id


CurrentOrgId = Annotated[str, Depends(get_current_org_id)]


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
            raise AuthorizationError(f"Role '{role}' is not permitted. Required: {[r.value for r in allowed]}")

    return Depends(dependency)


# Role guards — use in an endpoint's `dependencies=[...]` list.
InternalUserRole = require_role(Role.PROJECT_MANAGER, Role.REVIEWER, Role.APPROVER)  # any internal user
PMOnly = require_role(Role.PROJECT_MANAGER)
ReviewerRole = require_role(Role.PROJECT_MANAGER, Role.REVIEWER)
SupplierRole = require_role(Role.SUPPLIER)
