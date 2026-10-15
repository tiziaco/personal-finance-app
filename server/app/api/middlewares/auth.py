"""Authentication middleware for Clerk JWT token extraction and verification."""

from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.logging import logger
from app.exceptions.base import AuthUnavailableError
from app.utils.auth import clerk_jwt_verifier


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware for extracting and verifying Clerk JWT tokens.

    Stores the following in request.state on every request:
      - clerk_id   : Clerk user ID (sub claim), or None
      - user_id    : None here; set to the internal UUID after user provisioning
      - auth_error : the AuthUnavailableError when the token could not be checked,
        else None; get_clerk_id raises it, so the answer is 503, not 401

    The middleware is permissive — it does not block requests with invalid/missing
    tokens. Route-level dependencies determine if authentication is required.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Parse the Clerk token, if any, and stash the identity on request.state."""
        request.state.clerk_id = None
        request.state.user_id = None
        request.state.auth_error = None

        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            try:
                token = auth_header.split(" ")[1]
                payload = clerk_jwt_verifier.verify_token(token)

                if payload:
                    request.state.clerk_id = payload.get("sub")

                    logger.debug(
                        "token_verified_in_middleware",
                        clerk_id=request.state.clerk_id,
                        path=request.url.path,
                    )
                else:
                    logger.debug("token_verification_failed_in_middleware", path=request.url.path)

            except AuthUnavailableError as e:
                # Permissive, like everything here: kept for get_clerk_id, which raises it.
                request.state.auth_error = e
                logger.error("auth_unavailable_in_middleware", error=str(e), path=request.url.path)
            except (IndexError, ValueError) as e:
                logger.debug("token_extraction_failed", error=str(e), path=request.url.path)
        elif request.url.path not in ("/health", "/metrics"):
            logger.debug("no_auth_header_present", path=request.url.path)

        response = await call_next(request)
        return response
