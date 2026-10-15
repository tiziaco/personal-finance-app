"""Rate limiting configuration for the application.

This module configures rate limiting using slowapi, with default limits
defined in the application settings. Rate limits are applied based on
remote IP addresses, or by the caller with `user_or_ip_key`.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

from app.core.config import settings

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address, default_limits=settings.rate_limits.DEFAULT)


def user_or_ip_key(request: Request) -> str:
    """The signed-in caller's Clerk id, else the remote address: a per-user limit on authenticated routes.

    AuthMiddleware sets request.state.clerk_id before any route runs.
    """
    clerk_id = getattr(request.state, "clerk_id", None)
    return f"user:{clerk_id}" if clerk_id else get_remote_address(request)
