"""Clerk service package for interacting with Clerk Backend API."""

from app.services.clerk.exceptions import (
    ClerkAPIError,
    ClerkAuthenticationError,
    ClerkRateLimitError,
    ClerkServiceError,
    ClerkUserNotFoundError,
)
from app.services.clerk.service import (
    ClerkService,
    clerk_service,
)

__all__ = [
    "ClerkService",
    "clerk_service",
    "ClerkServiceError",
    "ClerkUserNotFoundError",
    "ClerkAPIError",
    "ClerkRateLimitError",
    "ClerkAuthenticationError",
]
