"""Integration tests for DELETE /api/v1/auth/me — GDPR erasure and cache cleanup."""

from unittest.mock import AsyncMock, patch

import pytest

from app.models.supplier import Supplier
from app.services.user.cache import (
    _MISS,
    user_cache,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def mocked_externals():
    """Stub the external side effects of account deletion (Clerk, mem0)."""
    with (
        patch("app.api.v1.auth.user_service.delete_user_from_clerk", new=AsyncMock()) as clerk,
        patch("app.api.v1.auth.delete_user_memory", new=AsyncMock()) as memory,
    ):
        yield {"clerk": clerk, "memory": memory}


class TestDeleteMeCacheInvalidation:
    """Account deletion must not leave cached auth data behind.

    Both caches are keyed differently — org role by clerk_id, supplier link
    by user_id — so clearing one is not enough.
    """

    async def test_clears_both_caches(
        self, authenticated_client_with_agent, test_user, mocked_externals
    ):
        await user_cache.set_org_role(test_user.clerk_id, "supplier")
        await user_cache.set_supplier_id(test_user.id, "supplier_42")
        original_clerk_id = test_user.clerk_id

        response = await authenticated_client_with_agent.delete("/api/v1/auth/me")

        assert response.status_code == 204
        assert await user_cache.get_org_role(original_clerk_id) is _MISS
        assert await user_cache.get_supplier_id(test_user.id) is _MISS

    async def test_uses_pre_anonymisation_clerk_id(
        self, authenticated_client_with_agent, test_user, mocked_externals
    ):
        """The role is cached under the ORIGINAL clerk_id.

        anonymize_user() rewrites user.clerk_id during the flow, so invalidating
        with the post-anonymisation value would clear the wrong key and leave
        the real entry behind.
        """
        original_clerk_id = test_user.clerk_id
        await user_cache.set_org_role(original_clerk_id, "project_manager")

        response = await authenticated_client_with_agent.delete("/api/v1/auth/me")

        assert response.status_code == 204
        assert test_user.clerk_id != original_clerk_id  # anonymised in-flight
        assert await user_cache.get_org_role(original_clerk_id) is _MISS

    async def test_supplier_is_unlinked(
        self, authenticated_client_with_agent, test_user, db_session, mocked_externals
    ):
        """Supplier.contact_id must not keep pointing at the erased user."""
        supplier = Supplier(
            contact_id=test_user.id,
            name="Acme Forgings",
            code="ACME-DEL",
            vat_number="IT99999999999",
        )
        db_session.add(supplier)
        await db_session.flush()

        response = await authenticated_client_with_agent.delete("/api/v1/auth/me")

        assert response.status_code == 204
        await db_session.refresh(supplier)
        assert supplier.contact_id is None

    async def test_org_id_is_cleared(
        self, authenticated_client_with_agent, test_user, mocked_externals
    ):
        """org_id is dropped so a single-contact supplier org cannot single the user out."""
        response = await authenticated_client_with_agent.delete("/api/v1/auth/me")

        assert response.status_code == 204
        assert test_user.org_id is None

    async def test_unrelated_users_are_untouched(
        self, authenticated_client_with_agent, test_user, mocked_externals
    ):
        await user_cache.set_org_role("clerk_someone_else", "reviewer")
        await user_cache.set_supplier_id("user_someone_else", "supplier_99")

        response = await authenticated_client_with_agent.delete("/api/v1/auth/me")

        assert response.status_code == 204
        assert await user_cache.get_org_role("clerk_someone_else") == "reviewer"
        assert await user_cache.get_supplier_id("user_someone_else") == "supplier_99"
