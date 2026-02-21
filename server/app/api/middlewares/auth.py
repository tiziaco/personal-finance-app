"""Authentication middleware for Clerk JWT token extraction and verification."""

from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.logging import logger
from app.utils.auth import clerk_jwt_verifier


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware for extracting and verifying Clerk JWT tokens.

    This middleware runs early in the request lifecycle to:
    - Extract JWT token from Authorization header
    - Verify token signature using Clerk's JWKS (RS256)
    - Store clerk_id (sub claim) in request.state.clerk_id for downstream use

    The middleware is permissive - it does not block requests with invalid/missing tokens.
    Route-level dependencies determine if authentication is required.

    Note: After user provisioning, request.state.user_id will be set to the internal UUID.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Extract and verify Clerk JWT token, storing clerk_id in request.state.

        Args:
            request: The incoming request
            call_next: The next middleware or route handler

        Returns:
            Response: The response from the application
        """
        request.state.clerk_id = None
        request.state.user_id = None

        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            try:
                token = auth_header.split(" ")[1]

                payload = clerk_jwt_verifier.verify_token(token)
                if payload:
                    request.state.clerk_id = payload.get("sub")  # Clerk ID

                    logger.debug(
                        "token_verified_in_middleware",
                        clerk_id=request.state.clerk_id,
                        path=request.url.path,
                    )
                else:
                    logger.debug(
                        "token_verification_failed_in_middleware",
                        path=request.url.path,
                    )

            except (IndexError, ValueError) as e:
                logger.debug(
                    "token_extraction_failed",
                    error=str(e),
                    path=request.url.path,
                )
        else:
            logger.debug(
                "no_auth_header_present",
                path=request.url.path,
            )

        response = await call_next(request)
        return response
