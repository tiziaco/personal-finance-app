"""Authentication middleware for Clerk JWT token extraction and verification."""

from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.logging import logger
from app.utils.auth import clerk_jwt_verifier


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware for extracting and verifying Clerk JWT tokens.

    Stores the following in request.state after a valid token:
      - clerk_id  : Clerk user ID (sub claim)
      - org_id    : Clerk organisation ID (org_id claim), or None
      - org_role  : Role slug with 'org:' prefix stripped (org_role claim), or None

    The middleware is permissive — it does not block requests with invalid/missing
    tokens. Route-level dependencies determine if authentication is required.

    Note: after user provisioning, request.state.user_id is set to the internal UUID.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request.state.clerk_id = None
        request.state.user_id = None
        request.state.org_id = None
        request.state.org_role = None

        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            try:
                token = auth_header.split(" ")[1]
                payload = clerk_jwt_verifier.verify_token(token)

                if payload:
                    request.state.clerk_id = payload.get("sub")

                    # Clerk JWT v2 (SDK ≥ v5): org claims nested under "o"
                    org_data = payload.get("o") or {}
                    request.state.org_id = org_data.get("id")
                    request.state.org_role = org_data.get("rol") or None

                    logger.debug(
                        "token_verified_in_middleware",
                        clerk_id=request.state.clerk_id,
                        org_id=request.state.org_id,
                        org_role=request.state.org_role,
                        path=request.url.path,
                    )
                else:
                    logger.debug("token_verification_failed_in_middleware", path=request.url.path)

            except (IndexError, ValueError) as e:
                logger.debug("token_extraction_failed", error=str(e), path=request.url.path)
        elif request.url.path not in ("/health", "/metrics"):
            logger.debug("no_auth_header_present", path=request.url.path)

        response = await call_next(request)
        return response
