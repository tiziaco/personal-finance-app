"""Integration tests for role-based access control dependencies."""

import pytest
from fastapi import APIRouter

from app.api.dependencies.auth import (
    InternalUserRole,
    PMOnly,
    SupplierRole,
    get_current_role,
)
from app.main import app
from app.models.enums import Role

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module", autouse=True)
def role_test_routes():
    """Mount sentinel endpoints with role guards for the duration of this module."""
    router = APIRouter(prefix="/_test/rbac")

    @router.get("/pm-only", dependencies=[PMOnly])
    async def _pm():
        return {"ok": True}

    @router.get("/internal", dependencies=[InternalUserRole])
    async def _internal():
        return {"ok": True}

    @router.get("/supplier-only", dependencies=[SupplierRole])
    async def _supplier():
        return {"ok": True}

    original_routes = list(app.router.routes)
    app.include_router(router)
    yield
    app.router.routes[:] = original_routes


def _set_role(role: Role) -> None:
    app.dependency_overrides[get_current_role] = lambda: role


class TestPMOnly:
    async def test_pm_passes(self, authenticated_client):
        _set_role(Role.PROJECT_MANAGER)
        response = await authenticated_client.get("/_test/rbac/pm-only")
        assert response.status_code == 200

    async def test_reviewer_blocked(self, authenticated_client):
        _set_role(Role.REVIEWER)
        response = await authenticated_client.get("/_test/rbac/pm-only")
        assert response.status_code == 403

    async def test_supplier_blocked(self, authenticated_client):
        _set_role(Role.SUPPLIER)
        response = await authenticated_client.get("/_test/rbac/pm-only")
        assert response.status_code == 403


class TestInternalUserRole:
    async def test_pm_passes(self, authenticated_client):
        _set_role(Role.PROJECT_MANAGER)
        response = await authenticated_client.get("/_test/rbac/internal")
        assert response.status_code == 200

    async def test_reviewer_passes(self, authenticated_client):
        _set_role(Role.REVIEWER)
        response = await authenticated_client.get("/_test/rbac/internal")
        assert response.status_code == 200

    async def test_approver_passes(self, authenticated_client):
        _set_role(Role.APPROVER)
        response = await authenticated_client.get("/_test/rbac/internal")
        assert response.status_code == 200

    async def test_supplier_blocked(self, authenticated_client):
        _set_role(Role.SUPPLIER)
        response = await authenticated_client.get("/_test/rbac/internal")
        assert response.status_code == 403


class TestSupplierRole:
    async def test_supplier_passes(self, authenticated_client):
        _set_role(Role.SUPPLIER)
        response = await authenticated_client.get("/_test/rbac/supplier-only")
        assert response.status_code == 200

    async def test_pm_blocked(self, authenticated_client):
        _set_role(Role.PROJECT_MANAGER)
        response = await authenticated_client.get("/_test/rbac/supplier-only")
        assert response.status_code == 403


class TestMissingRole:
    async def test_no_role_returns_403(self, client):
        # No get_current_role override — request.state.org_role is None,
        # so get_current_role raises AuthorizationError → 403.
        response = await client.get("/_test/rbac/pm-only")
        assert response.status_code == 403
