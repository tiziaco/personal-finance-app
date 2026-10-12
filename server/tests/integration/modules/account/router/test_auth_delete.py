"""Integration tests for DELETE /api/v1/auth/me — GDPR erasure."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.modules.conversation.models import Conversation

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


class TestDeleteMeOverHttp:
    """The route end to end: Clerk first, then the cascade, then a 204."""

    async def test_delete_me_deletes_in_clerk_anonymises_user_and_soft_deletes_conversations(
        self, authenticated_client_with_agent, test_user, db_session, mocked_externals
    ):
        original_clerk_id = test_user.clerk_id
        conv = Conversation(user_id=test_user.id, name="Private chat")
        db_session.add(conv)
        await db_session.flush()

        response = await authenticated_client_with_agent.delete("/api/v1/auth/me")

        assert response.status_code == 204
        mocked_externals["clerk"].assert_awaited_once_with(original_clerk_id)

        await db_session.flush()  # the route does not flush; refresh would discard pending changes
        await db_session.refresh(test_user)
        assert test_user.anonymized_at is not None
        assert test_user.clerk_id == f"deleted_user_{test_user.id}"
        assert test_user.email == f"deleted_user_{test_user.id}@anonymized.local"
        assert test_user.first_name is None
        assert test_user.last_name is None
        assert test_user.avatar_url is None

        await db_session.refresh(conv)
        assert conv.deleted_at is not None
        assert conv.name == ""


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
