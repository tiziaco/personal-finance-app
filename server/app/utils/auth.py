"""Clerk JWT verification utilities using PyJWT + JWKS."""

from typing import (
    Any,
    Dict,
    Optional,
)

import jwt
from jwt import PyJWKClient

from app.core.config import settings
from app.core.logging import logger
from app.exceptions.base import AuthUnavailableError

# Clerk's backend SDK allows 5 s. Without it a server clock behind Clerk's refuses a token
# Clerk has just minted (iat/nbf ahead of us), the web's forced-refresh retry mints another
# that is refused the same way, and the user is signed out.
CLOCK_SKEW_SECONDS = 5


class ClerkJWTVerifier:
    """Verifies Clerk JWTs using JWKS (RS256).

    Caches the JWKS client internally. PyJWKClient handles
    key caching and rotation automatically.
    """

    def __init__(self):
        self._jwks_client: Optional[PyJWKClient] = None

    @property
    def jwks_client(self) -> PyJWKClient:
        """Lazy-initialize the JWKS client."""
        if self._jwks_client is None:
            self._jwks_client = PyJWKClient(
                settings.auth.jwks_url,
                cache_keys=True,
                lifespan=3600,
            )
        return self._jwks_client

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify a Clerk JWT token and return the payload.

        Args:
            token: The JWT token string.

        Returns:
            The decoded payload dict if valid, None if the credentials are bad.

        Raises:
            AuthUnavailableError: the token could not be checked (JWKS unreachable or
                misconfigured, or an unexpected failure) -- not the caller's fault.
        """
        if not token or not isinstance(token, str):
            logger.warning("token_invalid_format")
            return None

        try:
            jwks_client = self.jwks_client
        except jwt.PyJWKClientError as e:
            # Raised while building the client: CLERK_ISSUER is not an http(s) URL.
            logger.error("token_jwks_client_invalid", jwks_url=settings.auth.jwks_url, error=str(e))
            raise AuthUnavailableError("The signing-key service is misconfigured") from e

        try:
            signing_key = jwks_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                issuer=settings.auth.ISSUER,
                leeway=CLOCK_SKEW_SECONDS,
                options={
                    "verify_exp": True,
                    "verify_iss": True,
                    "verify_aud": False,
                },
            )
            if not payload.get("sub"):
                logger.warning("token_missing_subject")
                return None

            # Session tokens (frontend getToken()) carry azp = issuing origin.
            # OAuth access tokens (Swagger's /docs Authorize flow) carry no azp
            # at all -- they're scoped to a registered OAuth client instead.
            azp = payload.get("azp")
            client_id = payload.get("client_id")
            authorized = azp in settings.cors.ALLOWED_ORIGINS or (
                client_id is not None and client_id == settings.auth.OAUTH_CLIENT_ID
            )
            if not authorized:
                logger.warning("token_party_not_allowed", azp=azp, client_id=client_id)
                return None

            logger.debug("token_verified", user_id=payload["sub"])
            return payload

        except jwt.ExpiredSignatureError:
            logger.debug("token_expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.debug("token_verification_failed", error=str(e))
            return None
        except jwt.PyJWKClientConnectionError as e:
            logger.error("token_jwks_unreachable", error=str(e))
            raise AuthUnavailableError("Could not reach the signing-key service") from e
        except jwt.PyJWKClientError as e:
            # The key lookup found no key for this token's kid: the token is wrong, not the service.
            logger.debug("token_signing_key_not_found", error=str(e))
            return None
        except Exception as e:
            logger.error("token_verification_error", error=str(e))
            raise AuthUnavailableError("Could not verify the token") from e


# Singleton verifier instance
clerk_jwt_verifier = ClerkJWTVerifier()
