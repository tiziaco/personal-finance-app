"""Integration test fixtures — real DB, mocked external services, short-circuit auth."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver

from app.agents.chatbot import ChatbotAgent, build_chatbot
from app.main import app
from app.modules.account import get_current_user
from app.modules.account.models import User
from app.modules.conversation import chat_preamble, chat_tools, get_chatbot_agent
from tests.fakes.chat_model import ScriptedChatModel


@pytest_asyncio.fixture
async def test_user(db_session):
    """Create a test user in the database, rolled back after each test."""
    user = User(
        clerk_id="user_test_integration_abc123",
        email="integration@example.com",
        first_name="Test",
        last_name="User",
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def authenticated_client(client, test_user):
    """HTTP client with get_current_user overridden to return test_user directly.

    Bypasses JWT verification and JIT provisioning entirely.
    The DB session is still active — routes can still write to DB.
    """
    app.dependency_overrides[get_current_user] = lambda: test_user
    yield client
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def scripted_model():
    """The chat model behind `agent`: answers "Hi there!" unless a test scripts more.

    Set `scripted_model.responses[:] = [...]` to script a turn; `sent` holds every request.
    """
    return ScriptedChatModel(responses=[AIMessage(content="Hi there!")])


@pytest.fixture
def agent(scripted_model):
    """The real chat agent, as `main.py` builds it, on a MemorySaver and the scripted model.

    The graph, the middleware, the seven tools and the preamble all run; only the model
    and mem0 are stand-ins (nothing relevant in memory, and the write goes nowhere).
    """
    with (
        patch("app.agents.chatbot.middleware.memory.get_relevant_memory", new=AsyncMock(return_value="")),
        patch("app.agents.chatbot.middleware.memory.update_memory", new=AsyncMock()),
    ):
        yield ChatbotAgent(
            build_chatbot(MemorySaver(), chat_tools(), chat_preamble, model=scripted_model), chat_tools()
        )


@pytest.fixture
def stub_checkpoint_deletion():
    """Stub LangGraph checkpoint deletion for routes that clear a conversation.

    The checkpoint tables live behind the psycopg pool that agents open at
    startup; no integration test opens it, so a real call blocks until
    PoolTimeout. This used to be stubbed incidentally, via the mocked agent
    that owned clear_chat_history. Now that deletion is a module-level
    function its callers import directly, every importing module needs
    patching by name — the two routes that clear a conversation, and
    UserService.erase_user, which clears the checkpoints of every
    conversation the deleted user owned.

    Yields the erasure path's stub, since that is the one a test asserts on:
    the routes' calls are incidental cleanup, while the conversation handler's
    are a contractual step of the GDPR cascade. The handler calls the plural
    once, with every conversation id the user owns.
    """
    with (
        patch("app.modules.conversation.router.chatbot.delete_conversation_checkpoints", new=AsyncMock()),
        patch("app.modules.conversation.router.conversation.delete_conversation_checkpoints", new=AsyncMock()),
        patch(
            "app.modules.conversation.handlers.delete_conversations_checkpoints",
            new=AsyncMock(),
        ) as erasure_stub,
    ):
        yield erasure_stub


@pytest_asyncio.fixture
async def authenticated_client_with_agent(authenticated_client, agent, db_session):
    """HTTP client with auth overridden and the chat routes on the real `agent`.

    The chat routes put `app.state.session_factory` in the turn's context for the
    preamble and the tools, and no lifespan sets it under test. It hands out the
    test's own session, so they read the rows the test seeded; whatever was there
    before is put back, so tests relying on its absence (`unauthenticated_client`)
    are unaffected.
    """

    @asynccontextmanager
    async def sessions():
        yield db_session

    app.dependency_overrides[get_chatbot_agent] = lambda: agent
    with patch.object(app.state, "session_factory", sessions, create=True):
        yield authenticated_client
    app.dependency_overrides.pop(get_chatbot_agent, None)
