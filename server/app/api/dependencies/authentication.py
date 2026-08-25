"""Authentication dependencies — identity resolution only.

Resource and role-based authorization guards live in `authorization.py`.
"""

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import OAuth2AuthorizationCodeBearer

from app.api.dependencies.database import DbSession
from app.core.config import settings
from app.core.logging import bind_context, logger
from app.exceptions.base import AuthenticationError, AuthorizationError
from app.models.enums import Role
from app.models.user import User
from app.services.user import user_service
from app.services.user.exceptions import SupplierNotLinkedError

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
        user = await user_service.resolve_user(clerk_id, org_id, session)
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
    Clerk's org membership API (cached 5 min via UserService).

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


# ---------------------------------------------------------------------------
# Identity type aliases
# ---------------------------------------------------------------------------

CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentRole = Annotated[Role, Depends(get_current_role)]


# ---------------------------------------------------------------------------
# Supplier-scoped identity — resolves caller's supplier_id
# ---------------------------------------------------------------------------


async def get_supplier_id(
    current_user: CurrentUser,
    session: DbSession,
) -> str:
    """Resolve the supplier_id linked to the current user.

    Flow: UserService.get_supplier_id_for_user (cache-first; DB fallback).
    Raises 403 SUPPLIER_NOT_LINKED if no Supplier.contact_id points at this user.

    Usage (value dep):
        async def handler(supplier_id: SupplierID, ...): ...
    """
    supplier_id = await user_service.get_supplier_id_for_user(
        user_id=current_user.id,
        session=session,
    )
    if supplier_id is None:
        raise SupplierNotLinkedError(
            "User is not linked to a supplier — accept the invitation first",
            user_id=current_user.id,
        )
    return supplier_id


SupplierID = Annotated[str, Depends(get_supplier_id)]
