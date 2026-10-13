"""Integration tests for chatbot endpoints — chat, stream, history, clear."""

import asyncio
import json
import uuid

import pytest
from uuid_utils.compat import uuid7

from app.modules.conversation.models import Conversation

pytestmark = pytest.mark.integration


@pytest.fixture
async def test_conversation(db_session, test_user):
    """A conversation owned by test_user for chatbot testing."""
    conv = Conversation(
        user_id=test_user.id,
        name="Chat Test",
    )
    db_session.add(conv)
    await db_session.flush()
    await db_session.refresh(conv)
    return conv


class TestChatEndpoint:
    """Tests for POST /api/v1/chatbot/chat/{conversation_id}"""

    async def test_unauthenticated_returns_401(self, client, test_conversation):
        response = await client.post(
            f"/api/v1/chatbot/chat/{test_conversation.id}",
            json={"message": "Hello"},
        )
        assert response.status_code == 401

    async def test_chat_returns_200_with_message(self, authenticated_client_with_agent, test_conversation):
        response = await authenticated_client_with_agent.post(
            f"/api/v1/chatbot/chat/{test_conversation.id}",
            json={"message": "Hello there"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert data["message"]["role"] == "assistant"
        assert data["message"]["content"] == "Hi there!"

    async def test_chat_nonexistent_conversation_returns_404(self, authenticated_client_with_agent):
        response = await authenticated_client_with_agent.post(
            f"/api/v1/chatbot/chat/{uuid7()}",
            json={"message": "Hello"},
        )
        assert response.status_code == 404

    async def test_chat_empty_message_returns_422(self, authenticated_client_with_agent, test_conversation):
        response = await authenticated_client_with_agent.post(
            f"/api/v1/chatbot/chat/{test_conversation.id}",
            json={"message": ""},
        )
        assert response.status_code == 422

    async def test_chat_other_users_conversation_returns_404(self, db_session, authenticated_client_with_agent):
        from app.modules.account.models import User

        other_user = User(clerk_id="clerk_chat_other", email="chat_other@example.com")
        db_session.add(other_user)
        await db_session.flush()
        await db_session.refresh(other_user)

        other_conv = Conversation(
            user_id=other_user.id,
            name="Other's Chat",
        )
        db_session.add(other_conv)
        await db_session.flush()

        response = await authenticated_client_with_agent.post(
            f"/api/v1/chatbot/chat/{other_conv.id}",
            json={"message": "Hello"},
        )
        assert response.status_code == 404

    async def test_chat_script_tag_returns_422(self, authenticated_client_with_agent, test_conversation):
        response = await authenticated_client_with_agent.post(
            f"/api/v1/chatbot/chat/{test_conversation.id}",
            json={"message": "<script>alert(1)</script>"},
        )
        assert response.status_code == 422


class TestStreamChatEndpoint:
    """Tests for POST /api/v1/chatbot/chat/{conversation_id}/stream"""

    async def test_stream_returns_event_stream(self, authenticated_client_with_agent, test_conversation, mock_agent):
        # Override get_stream_response to use an async generator
        async def mock_stream(*args, **kwargs):
            for chunk in ["Hello", " World"]:
                yield chunk

        mock_agent.get_stream_response = mock_stream

        response = await authenticated_client_with_agent.post(
            f"/api/v1/chatbot/chat/{test_conversation.id}/stream",
            json={"message": "Hello"},
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

    async def test_stream_response_contains_sse_data(
        self, authenticated_client_with_agent, test_conversation, mock_agent
    ):
        async def mock_stream(*args, **kwargs):
            for chunk in ["Hi!"]:
                yield chunk

        mock_agent.get_stream_response = mock_stream

        response = await authenticated_client_with_agent.post(
            f"/api/v1/chatbot/chat/{test_conversation.id}/stream",
            json={"message": "Hello"},
        )
        content = response.text
        # SSE format: "data: {...}\n\n"
        assert "data:" in content
        # Parse first event
        first_line = [line for line in content.split("\n") if line.startswith("data:")][0]
        payload = json.loads(first_line.replace("data: ", ""))
        assert "content" in payload
        assert "done" in payload


class TestGetChatHistory:
    """Tests for GET /api/v1/chatbot/chat/{conversation_id}/messages"""

    async def test_unauthenticated_returns_401(self, client, test_conversation):
        response = await client.get(f"/api/v1/chatbot/chat/{test_conversation.id}/messages")
        assert response.status_code == 401

    async def test_returns_conversation_history(self, authenticated_client_with_agent, test_conversation):
        response = await authenticated_client_with_agent.get(f"/api/v1/chatbot/chat/{test_conversation.id}/messages")
        assert response.status_code == 200
        data = response.json()
        assert "messages" in data
        assert len(data["messages"]) == 2  # from mock_agent fixture

    async def test_history_messages_have_role_and_content(self, authenticated_client_with_agent, test_conversation):
        response = await authenticated_client_with_agent.get(f"/api/v1/chatbot/chat/{test_conversation.id}/messages")
        messages = response.json()["messages"]
        for msg in messages:
            assert "role" in msg
            assert "content" in msg

    async def test_long_reply_in_history_returns_200(
        self, authenticated_client_with_agent, test_conversation, mock_agent
    ):
        from app.agents.messages import Message

        mock_agent.get_chat_history.return_value = [
            Message(role="user", content="Explain budgeting"),
            Message(role="assistant", content="x" * 5000),
        ]
        response = await authenticated_client_with_agent.get(f"/api/v1/chatbot/chat/{test_conversation.id}/messages")
        assert response.status_code == 200
        assert len(response.json()["messages"][1]["content"]) == 5000


class TestClearChatHistory:
    """Tests for DELETE /api/v1/chatbot/chat/{conversation_id}/messages"""

    async def test_unauthenticated_returns_401(self, client, test_conversation):
        response = await client.delete(f"/api/v1/chatbot/chat/{test_conversation.id}/messages")
        assert response.status_code == 401

    async def test_clear_history_returns_204(
        self, authenticated_client_with_agent, test_conversation, stub_checkpoint_deletion
    ):
        response = await authenticated_client_with_agent.delete(
            f"/api/v1/chatbot/chat/{test_conversation.id}/messages"
        )
        assert response.status_code == 204
        assert response.content == b""


class TestStreamWireFormat:
    """The event shape is a published interface: WS7 must not move it."""

    async def test_events_are_byte_identical(self, authenticated_client_with_agent, test_conversation, mock_agent):
        async def mock_stream(*args, **kwargs):
            yield "Hi"
            yield " there"

        mock_agent.get_stream_response = mock_stream

        response = await authenticated_client_with_agent.post(
            f"/api/v1/chatbot/chat/{test_conversation.id}/stream",
            json={"message": "Hello"},
        )
        frames = [f for f in response.text.split("\n\n") if f and not f.startswith(":")]
        assert frames == [
            'data: {"content": "Hi", "done": false}',
            'data: {"content": " there", "done": false}',
            'data: {"content": "", "done": true}',
        ]

    async def test_failure_is_a_final_event_with_content(
        self, authenticated_client_with_agent, test_conversation, mock_agent
    ):
        async def failing_stream(*args, **kwargs):
            yield "partial"
            raise RuntimeError("model down")

        mock_agent.get_stream_response = failing_stream

        response = await authenticated_client_with_agent.post(
            f"/api/v1/chatbot/chat/{test_conversation.id}/stream",
            json={"message": "Hello"},
        )
        frames = [f for f in response.text.split("\n\n") if f and not f.startswith(":")]
        assert frames[-1] == 'data: {"content": "An error occurred. Please try again.", "done": true}'


class TestStreamClientDisconnect:
    """WS7: a client that leaves mid-stream stops the model call."""

    async def test_disconnect_cancels_the_agent_stream(
        self, authenticated_client_with_agent, test_conversation, mock_agent
    ):
        from app.main import app

        first_chunk_sent = asyncio.Event()
        cancelled = asyncio.Event()

        async def slow_stream(*args, **kwargs):
            try:
                yield "first"
                first_chunk_sent.set()
                await asyncio.sleep(30)  # a model still generating
                yield "never"
            except asyncio.CancelledError:
                cancelled.set()
                raise

        mock_agent.get_stream_response = slow_stream

        body = b'{"message": "Hello"}'
        request_sent = False

        async def receive():
            nonlocal request_sent
            if not request_sent:
                request_sent = True
                return {"type": "http.request", "body": body, "more_body": False}
            await first_chunk_sent.wait()
            return {"type": "http.disconnect"}

        async def send(message):
            pass

        path = f"/api/v1/chatbot/chat/{test_conversation.id}/stream"
        scope = {
            "type": "http",
            # At spec 2.4 Starlette's StreamingResponse stops listening for disconnects;
            # the generator must still be cancelled.
            "asgi": {"version": "3.0", "spec_version": "2.4"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "root_path": "",
            "query_string": b"",
            "headers": [(b"host", b"test"), (b"content-type", b"application/json")],
            "client": ("127.0.0.1", 12345),
            "server": ("test", 80),
        }

        await asyncio.wait_for(app(scope, receive, send), timeout=5)
        assert cancelled.is_set()
