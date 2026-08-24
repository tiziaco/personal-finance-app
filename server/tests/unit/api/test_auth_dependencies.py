"""Tests for role-based dependencies in app.api.dependencies.auth."""

import pytest
from unittest.mock import MagicMock
from fastapi import Request

from app.api.dependencies.auth import get_current_role
from app.exceptions.base import AuthorizationError
from app.models.enums import Role

pytestmark = pytest.mark.unit


def _make_request_with_role(role: str | None):
    """Create a mock Request with org_role in state."""
    request = MagicMock()
    request.state.org_role = role
    return request


class TestGetCurrentRole:
    def test_returns_role_enum_for_valid_role(self):
        request = _make_request_with_role("project_manager")
        result = get_current_role(request)
        assert result == Role.PROJECT_MANAGER

    def test_returns_supplier_role(self):
        request = _make_request_with_role("supplier")
        result = get_current_role(request)
        assert result == Role.SUPPLIER

    def test_raises_authorization_error_when_no_role(self):
        request = _make_request_with_role(None)
        with pytest.raises(AuthorizationError, match="No organization role"):
            get_current_role(request)

    def test_raises_authorization_error_for_unknown_role(self):
        request = _make_request_with_role("unknown_role")
        with pytest.raises(AuthorizationError, match="Unknown role"):
            get_current_role(request)


