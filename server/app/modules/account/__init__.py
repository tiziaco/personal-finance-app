"""Account — the Clerk-backed identity: the user row, the caller's identity, erasure.

This is the public surface. Another module imports from here and nowhere
deeper (docs/architecture/server.md, R1).

The dependency getter is exported alongside its Annotated alias on purpose:
FastAPI keys dependency_overrides by the exact callable, so get_current_user
is the only way a test can stand in for CurrentUser.
"""

from app.modules.account.dependencies import CurrentUser, get_current_user
from app.modules.account.exceptions import UserAlreadyExistsError
from app.modules.account.router import router
from app.modules.account.schemas import UserResponse
from app.modules.account.service import USER_ERASING, USER_SYNCED, user_service

__all__ = [
    "CurrentUser",
    "USER_ERASING",
    "USER_SYNCED",
    "UserAlreadyExistsError",
    "UserResponse",
    "get_current_user",
    "router",
    "user_service",
]
