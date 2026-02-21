"""Tests for app.utils.auth — ClerkJWTVerifier token verification."""

from unittest.mock import MagicMock, patch

import jwt as pyjwt
import pytest

from app.utils.auth import ClerkJWTVerifier

pytestmark = pytest.mark.unit


@pytest.fixture
def verifier():
    """Fresh ClerkJWTVerifier instance for each test."""
    return ClerkJWTVerifier()


class TestVerifyToken:
    """Tests for ClerkJWTVerifier.verify_token()."""

    @patch.object(ClerkJWTVerifier, "jwks_client", new_callable=lambda: property(lambda self: MagicMock()))
    @patch("app.utils.auth.jwt.decode")
    def test_valid_token_returns_payload(self, mock_decode, mock_jwks_prop):
        verifier = ClerkJWTVerifier()
        mock_decode.return_value = {"sub": "user_123", "exp": 9999999999}

        result = verifier.verify_token("valid.jwt.token")

        assert result == {"sub": "user_123", "exp": 9999999999}
        mock_decode.assert_called_once()

    @patch.object(ClerkJWTVerifier, "jwks_client", new_callable=lambda: property(lambda self: MagicMock()))
    @patch("app.utils.auth.jwt.decode")
    def test_expired_token_returns_none(self, mock_decode, mock_jwks_prop):
        verifier = ClerkJWTVerifier()
        mock_decode.side_effect = pyjwt.ExpiredSignatureError()

        result = verifier.verify_token("expired.jwt.token")
        assert result is None

    @patch.object(ClerkJWTVerifier, "jwks_client", new_callable=lambda: property(lambda self: MagicMock()))
    @patch("app.utils.auth.jwt.decode")
    def test_invalid_token_returns_none(self, mock_decode, mock_jwks_prop):
        verifier = ClerkJWTVerifier()
        mock_decode.side_effect = pyjwt.InvalidTokenError("bad token")

        result = verifier.verify_token("invalid.jwt.token")
        assert result is None

    @patch.object(ClerkJWTVerifier, "jwks_client", new_callable=lambda: property(lambda self: MagicMock()))
    @patch("app.utils.auth.jwt.decode")
    def test_missing_sub_returns_none(self, mock_decode, mock_jwks_prop):
        verifier = ClerkJWTVerifier()
        mock_decode.return_value = {"exp": 9999999999}  # no "sub"

        result = verifier.verify_token("no-sub.jwt.token")
        assert result is None

    def test_empty_token_returns_none(self, verifier):
        assert verifier.verify_token("") is None

    def test_none_token_returns_none(self, verifier):
        assert verifier.verify_token(None) is None

    def test_non_string_token_returns_none(self, verifier):
        assert verifier.verify_token(12345) is None

    @patch.object(ClerkJWTVerifier, "jwks_client", new_callable=lambda: property(lambda self: MagicMock()))
    def test_jwks_fetch_error_returns_none(self, mock_jwks_prop):
        verifier = ClerkJWTVerifier()
        # Make get_signing_key_from_jwt raise
        verifier.jwks_client.get_signing_key_from_jwt.side_effect = Exception("JWKS fetch failed")

        result = verifier.verify_token("some.jwt.token")
        assert result is None
