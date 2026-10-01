"""Integration tests for DELETE /api/v1/auth/me — GDPR erasure and cache cleanup."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.account.cache import user_cache
from app.modules.conversation.models import Conversation
from app.modules.supplier.cache import supplier_cache
from app.modules.supplier.models import Supplier
from app.utils.cache import MISS

pytestmark = pytest.mark.integration


@pytest.fixture
def mocked_externals(stub_checkpoint_deletion):
    """Stub the external side effects of account deletion.

    Clerk and mem0 are stubbed here; LangGraph checkpoint deletion comes from
    the shared fixture, which is what keeps erase_user() off the real psycopg
    pool. Taking it as a dependency rather than per-test means every test in
    this module is covered, including any added later that gives the deleted
    user a conversation.
    """
    with (
        patch("app.modules.account.router.auth.user_service.delete_user_from_clerk", new=AsyncMock()) as clerk,
        patch("app.modules.account.service.delete_user_memory", new=AsyncMock()) as memory,
    ):
        yield {"clerk": clerk, "memory": memory, "checkpoints": stub_checkpoint_deletion}


class TestDeleteMeCacheInvalidation:
    """Account deletion must not leave cached auth data behind.

    Both caches are keyed differently — org role by clerk_id, supplier link
    by user_id — so clearing one is not enough.
    """

    async def test_clears_both_caches(self, authenticated_client_with_agent, test_user, mocked_externals):
        await user_cache.set_org_role(test_user.clerk_id, "supplier")
        await supplier_cache.set_supplier_id(test_user.id, "supplier_42")
        original_clerk_id = test_user.clerk_id

        response = await authenticated_client_with_agent.delete("/api/v1/auth/me")

        assert response.status_code == 204
        assert await user_cache.get_org_role(original_clerk_id) is MISS
        assert await supplier_cache.get_supplier_id(test_user.id) is MISS

    async def test_uses_pre_anonymisation_clerk_id(self, authenticated_client_with_agent, test_user, mocked_externals):
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
        assert await user_cache.get_org_role(original_clerk_id) is MISS

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

    async def test_org_id_is_cleared(self, authenticated_client_with_agent, test_user, mocked_externals):
        """org_id is dropped so a single-contact supplier org cannot single the user out."""
        response = await authenticated_client_with_agent.delete("/api/v1/auth/me")

        assert response.status_code == 204
        assert test_user.org_id is None

    async def test_unrelated_users_are_untouched(self, authenticated_client_with_agent, test_user, mocked_externals):
        await user_cache.set_org_role("clerk_someone_else", "reviewer")
        await supplier_cache.set_supplier_id("user_someone_else", "supplier_99")

        response = await authenticated_client_with_agent.delete("/api/v1/auth/me")

        assert response.status_code == 204
        assert await user_cache.get_org_role("clerk_someone_else") == "reviewer"
        assert await supplier_cache.get_supplier_id("user_someone_else") == "supplier_99"


class TestDeleteMeCheckpointCleanup:
    """The erasure cascade must clear the checkpoints of every conversation.

    Checkpoints hold the message text and are keyed by conversation id, so
    they outlive anonymize_user() unless deleted first — nothing would point
    at them afterwards and nothing would ever clean them up.

    Until this class existed, no test in this module gave the deleted user a
    conversation, so the loop in erase_user() never ran and the missing stub
    went unnoticed. Unstubbed, it reaches the real psycopg pool that no
    integration test opens and blocks until PoolTimeout.
    """

    async def test_checkpoints_are_deleted_for_every_conversation(
        self, authenticated_client_with_agent, test_user, db_session, mocked_externals
    ):
        """One call carrying every conversation the user owned — none may be skipped."""
        conversations = [Conversation(user_id=test_user.id, name=f"Chat {i}") for i in range(2)]
        db_session.add_all(conversations)
        await db_session.flush()

        response = await authenticated_client_with_agent.delete("/api/v1/auth/me")

        assert response.status_code == 204
        mocked_externals["checkpoints"].assert_awaited_once()
        deleted = set(mocked_externals["checkpoints"].await_args.args[0])
        assert deleted == {conv.id for conv in conversations}

    async def test_checkpoints_are_deleted_for_conversations_deleted_before_erasure(
        self, authenticated_client_with_agent, test_user, db_session, mocked_externals
    ):
        """The guarantee lives here, not in the delete route.

        DELETE /conversation/{id} clears checkpoints before soft-deleting, so in
        practice these are already gone. Erasure must not depend on it.
        """
        active = Conversation(user_id=test_user.id, name="Active")
        earlier = Conversation(user_id=test_user.id, name="Deleted earlier")
        db_session.add_all([active, earlier])
        await db_session.flush()
        earlier.soft_delete()
        db_session.add(earlier)
        await db_session.flush()

        response = await authenticated_client_with_agent.delete("/api/v1/auth/me")

        assert response.status_code == 204
        deleted = set(mocked_externals["checkpoints"].await_args.args[0])
        assert deleted == {active.id, earlier.id}

    async def test_checkpoints_are_deleted_before_anonymisation(
        self, authenticated_client_with_agent, test_user, db_session, mocked_externals
    ):
        """Step order is contractual, not incidental.

        anonymize_user() blanks Conversation.name and rewrites the user's
        identifiers, so a cascade that anonymised first would be deleting
        checkpoints keyed by values it had already destroyed.
        """
        conv = Conversation(user_id=test_user.id, name="Before")
        db_session.add(conv)
        await db_session.flush()

        recorded_names = []
        mocked_externals["checkpoints"].side_effect = lambda _ids: recorded_names.append(conv.name)

        response = await authenticated_client_with_agent.delete("/api/v1/auth/me")

        assert response.status_code == 204
        assert recorded_names == ["Before"]  # not yet blanked when the call was made
        assert conv.name == ""  # blanked afterwards
