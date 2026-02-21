"""Integration test fixtures — real DB, mocked external services, short-circuit auth."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock

from app.api.dependencies.agent import get_chatbot_agent
from app.api.dependencies.auth import get_current_user
from app.main import app
from app.models.user import User
from app.schemas.chat import Message

pytestmark = pytest.mark.integration


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
def mock_agent():
    """Mock ChatbotAgent with pre-configured async method stubs."""
    agent = MagicMock()
    agent.get_response = AsyncMock(return_value=[
        Message(role="user", content="Hello"),
        Message(role="assistant", content="Hi there!"),
    ])
    agent.get_chat_history = AsyncMock(return_value=[
        Message(role="user", content="Hello"),
        Message(role="assistant", content="Hi there!"),
    ])
    agent.clear_chat_history = AsyncMock(return_value=None)
    agent.llm_service.get_llm.return_value.get_name.return_value = "gpt-5-mini"
    agent.is_ready.return_value = True
    return agent


@pytest_asyncio.fixture
async def authenticated_client_with_agent(authenticated_client, mock_agent):
    """HTTP client with both auth and chatbot agent overridden."""
    app.dependency_overrides[get_chatbot_agent] = lambda: mock_agent
    yield authenticated_client
    app.dependency_overrides.pop(get_chatbot_agent, None)
