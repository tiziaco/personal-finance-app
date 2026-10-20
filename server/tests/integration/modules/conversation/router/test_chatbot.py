"""Integration tests for chatbot endpoints — chat, stream, history, clear."""

import asyncio
import json
import uuid

import pytest
from uuid_utils.compat import uuid7

from app.agents.chatbot.events import DoneEvent, TextEvent, ToolFinishedEvent, ToolStartedEvent
from app.agents.chatbot.toolkit import SummaryItem, TableColumn, ToolDisplay, ToolTable
from app.agents.messages import Activity, ChatMessage, ReasoningPart, ToolPart
from app.main import app
from app.modules.conversation.models import Conversation

pytestmark = pytest.mark.integration

DISPLAY = ToolDisplay(
    title="Spending by category",
    period="Sep 2026",
    summary=[SummaryItem(kind="money", value=2184.5, label="spent")],
    table=ToolTable(
        columns=[TableColumn(key="category", label="Category", kind="text")],
        rows=[{"category": "Groceries"}],
    ),
)


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

    async def test_chat_gives_the_agent_the_users_turn_context(
        self, authenticated_client_with_agent, test_conversation, mock_agent, test_user
    ):
        await authenticated_client_with_agent.post(
            f"/api/v1/chatbot/chat/{test_conversation.id}",
            json={"message": "Hello"},
        )
        ctx = mock_agent.get_response.await_args.args[2]
        assert ctx.user_id == test_user.id
        assert ctx.session_factory is app.state.session_factory


class TestStreamChatEndpoint:
    """Tests for POST /api/v1/chatbot/chat/{conversation_id}/stream"""

    async def test_stream_returns_event_stream(self, authenticated_client_with_agent, test_conversation, mock_agent):
        async def mock_stream(*args, **kwargs):
            yield TextEvent(text="Hello")
            yield DoneEvent()

        mock_agent.get_stream_response = mock_stream

        response = await authenticated_client_with_agent.post(
            f"/api/v1/chatbot/chat/{test_conversation.id}/stream",
            json={"message": "Hello"},
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

    async def test_the_agent_gets_the_users_turn_context(
        self, authenticated_client_with_agent, test_conversation, mock_agent, test_user
    ):
        received = {}

        async def mock_stream(messages, conversation_id, turn_context):
            received["ctx"] = turn_context
            yield DoneEvent()

        mock_agent.get_stream_response = mock_stream

        await authenticated_client_with_agent.post(
            f"/api/v1/chatbot/chat/{test_conversation.id}/stream",
            json={"message": "Hello"},
        )
        assert received["ctx"].user_id == test_user.id
        assert received["ctx"].session_factory is app.state.session_factory


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
        mock_agent.get_chat_history.return_value = [
            ChatMessage(role="user", content="Explain budgeting"),
            ChatMessage(role="assistant", content="x" * 5000),
        ]
        response = await authenticated_client_with_agent.get(f"/api/v1/chatbot/chat/{test_conversation.id}/messages")
        assert response.status_code == 200
        assert len(response.json()["messages"][1]["content"]) == 5000

    async def test_history_response_carries_activity(
        self, authenticated_client_with_agent, test_conversation, mock_agent
    ):
        mock_agent.get_chat_history.return_value = [
            ChatMessage(role="user", content="Where did my money go?"),
            ChatMessage(
                role="assistant",
                content="Mostly groceries.",
                activity=Activity(
                    parts=[
                        ReasoningPart(text="Checking categories."),
                        ToolPart(id="c1", name="spending", title="Spending by category", ok=True, display=DISPLAY),
                        ToolPart(id="c2", name="income", title="Income", ok=False, display=None),
                    ],
                    stopped=True,
                ),
            ),
        ]
        response = await authenticated_client_with_agent.get(f"/api/v1/chatbot/chat/{test_conversation.id}/messages")
        assert response.status_code == 200
        [user, reply] = response.json()["messages"]
        assert user == {"role": "user", "content": "Where did my money go?", "activity": None}
        assert reply["activity"] == {
            "parts": [
                {"type": "reasoning", "text": "Checking categories."},
                {
                    "type": "tool",
                    "id": "c1",
                    "name": "spending",
                    "title": "Spending by category",
                    "ok": True,
                    "display": DISPLAY.model_dump(),
                },
                {"type": "tool", "id": "c2", "name": "income", "title": "Income", "ok": False, "display": None},
            ],
            "stopped": True,
        }


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


def _events(response) -> list[dict]:
    frames = [f for f in response.text.split("\n\n") if f and not f.startswith(":")]
    assert all(f.startswith("data: ") for f in frames)
    return [json.loads(f.removeprefix("data: ")) for f in frames]


class TestStreamWireFormat:
    """The event shape is a published interface: `stream-chat.ts` parses it."""

    async def test_stream_emits_typed_events_ending_in_done(
        self, authenticated_client_with_agent, test_conversation, mock_agent
    ):
        async def mock_stream(*args, **kwargs):
            yield ToolStartedEvent(id="c1", name="spending", title="Looking up spending")
            yield ToolFinishedEvent(id="c1", ok=True, display=DISPLAY)
            yield TextEvent(text="You spent €40.")
            yield DoneEvent(stopped=False)

        mock_agent.get_stream_response = mock_stream

        response = await authenticated_client_with_agent.post(
            f"/api/v1/chatbot/chat/{test_conversation.id}/stream",
            json={"message": "Hello"},
        )
        events = _events(response)
        assert [e["type"] for e in events] == ["tool_started", "tool_finished", "text", "done"]
        assert events[0] == {"type": "tool_started", "id": "c1", "name": "spending", "title": "Looking up spending"}
        assert events[1]["display"] == DISPLAY.model_dump()
        assert events[2] == {"type": "text", "text": "You spent €40."}
        assert events[3] == {"type": "done", "stopped": False}

    async def test_stream_failure_is_an_error_event_without_server_text(
        self, authenticated_client_with_agent, test_conversation, mock_agent
    ):
        async def failing_stream(*args, **kwargs):
            yield TextEvent(text="partial")
            raise RuntimeError("model down")

        mock_agent.get_stream_response = failing_stream

        response = await authenticated_client_with_agent.post(
            f"/api/v1/chatbot/chat/{test_conversation.id}/stream",
            json={"message": "Hello"},
        )
        events = _events(response)
        assert events == [{"type": "text", "text": "partial"}, {"type": "error"}]


class TestStreamClientDisconnect:
    """WS7: a client that leaves mid-stream stops the model call."""

    async def test_disconnect_cancels_the_agent_stream(
        self, authenticated_client_with_agent, test_conversation, mock_agent
    ):
        first_chunk_sent = asyncio.Event()
        cancelled = asyncio.Event()

        async def slow_stream(*args, **kwargs):
            try:
                yield TextEvent(text="first")
                first_chunk_sent.set()
                await asyncio.sleep(30)  # a model still generating
                yield TextEvent(text="never")
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
