"""Authorization dependencies — role guards only.

Resource-ownership checks (e.g. "does this supplier own this order?") live
in the service layer. Deps in this module are stateless and do NOT touch
the database.
"""

from fastapi import Depends

from app.api.dependencies.authentication import get_current_role
from app.exceptions.base import AuthorizationError
from app.models.enums import Role


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
