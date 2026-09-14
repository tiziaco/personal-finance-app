"""Tests for role-based dependencies in app.api.dependencies.auth."""

from unittest.mock import MagicMock

import pytest

from app.api.dependencies.authentication import get_current_role
from app.exceptions.base import AuthorizationError
from app.models.enums import Role

pytestmark = pytest.mark.unit


def _make_request_with_role(role: str | None, clerk_id: str | None = None):
    """Create a mock Request with org_role in state.

    `clerk_id` defaults to None on purpose: MagicMock would otherwise
    auto-create a truthy attribute, sending get_current_role down the
    resolve_org_role fallback and out to the real Clerk API.
    """
    request = MagicMock()
    request.state.org_role = role
    request.state.clerk_id = clerk_id
    return request


class TestGetCurrentRole:
    async def test_returns_role_enum_for_valid_role(self):
        request = _make_request_with_role("project_manager")
        result = await get_current_role(request)
        assert result == Role.PROJECT_MANAGER

    async def test_returns_supplier_role(self):
        request = _make_request_with_role("supplier")
        result = await get_current_role(request)
        assert result == Role.SUPPLIER

    async def test_raises_authorization_error_when_no_role(self):
        request = _make_request_with_role(None)
        with pytest.raises(AuthorizationError, match="No organization role"):
            await get_current_role(request)

    async def test_raises_authorization_error_for_unknown_role(self):
        request = _make_request_with_role("unknown_role")
        with pytest.raises(AuthorizationError, match="Unknown role"):
            await get_current_role(request)
