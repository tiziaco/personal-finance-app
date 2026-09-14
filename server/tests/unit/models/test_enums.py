"""Tests for app.models.enums."""

import pytest

from app.models.enums import Role

pytestmark = pytest.mark.unit


class TestRole:
    def test_all_roles_defined(self):
        assert Role.PROJECT_MANAGER == "project_manager"
        assert Role.REVIEWER == "reviewer"
        assert Role.APPROVER == "approver"
        assert Role.SUPPLIER == "supplier"

    def test_role_from_string(self):
        assert Role("project_manager") == Role.PROJECT_MANAGER

    def test_role_invalid_string_raises(self):
        with pytest.raises(ValueError):
            Role("admin")

    def test_role_is_str(self):
        assert isinstance(Role.PROJECT_MANAGER, str)
