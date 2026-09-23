"""Account — the Clerk-backed identity: the user row, the caller's identity, role and organisation, erasure.

This is the public surface. Another module imports from here and nowhere
deeper (docs/architecture/server-modules.md, R1).

The dependency *getters* are exported alongside their Annotated aliases on
purpose: FastAPI keys dependency_overrides by the exact callable, so
get_current_user is the only way a test can stand in for CurrentUser.
"""

from app.modules.account.dependencies import (
    CurrentOrgId,
    CurrentRole,
    CurrentUser,
    InternalUserRole,
    PMOnly,
    ReviewerRole,
    SupplierRole,
    get_clerk_id,
    get_current_org_id,
    get_current_role,
    get_current_user,
    require_role,
)
from app.modules.account.exceptions import UserAlreadyExistsError
from app.modules.account.models import Role
from app.modules.account.router import router
from app.modules.account.schemas import UserResponse
from app.modules.account.service import USER_ERASING, USER_OFFBOARDED, USER_SYNCED, user_service

__all__ = [
    "CurrentOrgId",
    "CurrentRole",
    "CurrentUser",
    "InternalUserRole",
    "PMOnly",
    "ReviewerRole",
    "Role",
    "SupplierRole",
    "USER_ERASING",
    "USER_OFFBOARDED",
    "USER_SYNCED",
    "UserAlreadyExistsError",
    "UserResponse",
    "get_clerk_id",
    "get_current_org_id",
    "get_current_role",
    "get_current_user",
    "require_role",
    "router",
    "user_service",
]
