"""Integration tests for chatbot endpoints — chat, stream, history, clear."""

import asyncio
import datetime as dt
import json
import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import async_sessionmaker
from uuid_utils.compat import uuid7

from app.agents.chatbot import ChatbotAgent, build_chatbot
from app.core.config import settings
from app.main import app
from app.modules.analytics import service as analytics_service_module
from app.modules.conversation import chat_preamble, chat_tools, get_chatbot_agent
from app.modules.conversation.models import Conversation
from app.modules.conversation.schemas import SummaryItem, TableColumn, ToolDisplay, ToolTable

pytestmark = pytest.mark.integration

DISPLAY = ToolDisplay(
    title="Spending by category",
    period="Sep 2026",
    summary=[SummaryItem(kind="total", value="2184.50", label="spent")],
    table=ToolTable(
        columns=[TableColumn(key="category", label="Category", kind="text")],
        rows=[{"category": "Groceries"}],
    ),
)


class _NoArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


def stub_tool(name: str, title: str, artifact: dict | None = None) -> StructuredTool:
    """A tool of the test's own: it returns `artifact` as its display, or raises when there is none."""

    async def run() -> tuple[str, dict]:
        if artifact is None:
            raise RuntimeError(f"{name} is down")
        return f"{name} result", artifact

    return StructuredTool.from_function(
        coroutine=run,
        name=name,
        description=f"Looks up {name}.",
        args_schema=_NoArgs,
        response_format="content_and_artifact",
        metadata={"title": title},
    )


def tool_call(name: str, call_id: str, **args) -> dict:
    return {"name": name, "args": args, "id": call_id, "type": "tool_call"}


@pytest.fixture
def use_tools(agent, scripted_model):
    """Put the chat routes on an agent built with the given tools instead of the chat's own.

    Depends on `agent` for its mem0 stubs; the scripted model is the same one.
    """

    def use(*tools: StructuredTool) -> ChatbotAgent:
        built = ChatbotAgent(build_chatbot(MemorySaver(), tools, chat_preamble, model=scripted_model), tools)
        app.dependency_overrides[get_chatbot_agent] = lambda: built
        return built

    return use


@pytest.fixture
async def seeded_lookup(add, test_user, other_user, scripted_model, monkeypatch):
    """September spending for test_user and for another user, and a model that looks up last month."""
    monkeypatch.setattr(analytics_service_module, "_today", lambda: dt.date(2026, 10, 16))
    await add(test_user, "2026-09-05", "-180.50", merchant="Lidl")
    await add(other_user, "2026-09-07", "-9999.00", merchant="Secret Boutique")
    scripted_model.responses[:] = [
        AIMessage(content="", tool_calls=[tool_call("spending_overview", "c1", months=1)]),
        AIMessage(content="You spent €180.50 in September 2026."),
    ]


def _spent(display: dict) -> str:
    return next(item for item in display["summary"] if item["label"] == "spent")["value"]


@pytest.fixture
def separate_sessions(authenticated_client_with_agent, test_engine):
    """Turn sessions of their own, as in production, so the request's session is the only one on `db_session`.

    Inside `authenticated_client_with_agent`, whose test-session factory it stands in for and then gives back
    by hand: `patch.object` cannot see that starlette's `State` held the attribute, and would delete it.
    """
    previous = app.state.session_factory
    app.state.session_factory = async_sessionmaker(test_engine)
    yield
    app.state.session_factory = previous


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
        self, authenticated_client_with_agent, test_conversation, agent, test_user, seeded_lookup
    ):
        with patch.object(agent, "run", wraps=agent.run) as run:
            response = await authenticated_client_with_agent.post(
                f"/api/v1/chatbot/chat/{test_conversation.id}",
                json={"message": "Hello"},
            )
        ctx = run.await_args.args[2]
        assert ctx.user_id == test_user.id
        assert ctx.session_factory is app.state.session_factory
        # Through a lookup: the tool read this user's spending, not the other user's.
        [part] = response.json()["message"]["activity"]["parts"]
        assert _spent(part["display"]) == "180.50"
        assert "9999" not in response.text

    async def test_chat_releases_the_connection_before_the_model_call(
        self, authenticated_client_with_agent, test_conversation, scripted_model, db_session, separate_sessions
    ):
        seen = {}

        async def respond(*_):
            seen["in_transaction"] = db_session.in_transaction()
            return AIMessage(content="Hi")

        scripted_model.responses[:] = [respond]

        await authenticated_client_with_agent.post(
            f"/api/v1/chatbot/chat/{test_conversation.id}", json={"message": "Hello"}
        )
        assert seen["in_transaction"] is False


class TestStreamChatEndpoint:
    """Tests for POST /api/v1/chatbot/chat/{conversation_id}/stream"""

    async def test_stream_returns_event_stream(
        self, authenticated_client_with_agent, test_conversation, scripted_model
    ):
        scripted_model.responses[:] = [AIMessage(content="Hello")]

        response = await authenticated_client_with_agent.post(
            f"/api/v1/chatbot/chat/{test_conversation.id}/stream",
            json={"message": "Hello"},
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

    async def test_the_agent_gets_the_users_turn_context(
        self, authenticated_client_with_agent, test_conversation, agent, test_user, seeded_lookup
    ):
        with patch.object(agent, "stream", wraps=agent.stream) as stream:
            response = await authenticated_client_with_agent.post(
                f"/api/v1/chatbot/chat/{test_conversation.id}/stream",
                json={"message": "Hello"},
            )
        received = {"ctx": stream.call_args.args[2]}
        assert received["ctx"].user_id == test_user.id
        assert received["ctx"].session_factory is app.state.session_factory
        # Through a lookup: the tool read this user's spending, not the other user's.
        [finished] = [e for e in _events(response) if e["type"] == "tool_finished"]
        assert _spent(finished["display"]) == "180.50"
        assert "9999" not in response.text

    async def test_stream_releases_the_connection_before_the_model_call(
        self, authenticated_client_with_agent, test_conversation, scripted_model, db_session, separate_sessions
    ):
        seen = {}

        async def respond(*_):
            seen["in_transaction"] = db_session.in_transaction()
            return AIMessage(content="Hi")

        scripted_model.responses[:] = [respond]

        await authenticated_client_with_agent.post(
            f"/api/v1/chatbot/chat/{test_conversation.id}/stream", json={"message": "Hello"}
        )
        assert seen["in_transaction"] is False


class TestGetChatHistory:
    """Tests for GET /api/v1/chatbot/chat/{conversation_id}/messages"""

    async def test_unauthenticated_returns_401(self, client, test_conversation):
        response = await client.get(f"/api/v1/chatbot/chat/{test_conversation.id}/messages")
        assert response.status_code == 401

    async def test_returns_conversation_history(self, authenticated_client_with_agent, test_conversation):
        await authenticated_client_with_agent.post(
            f"/api/v1/chatbot/chat/{test_conversation.id}", json={"message": "Hello"}
        )
        response = await authenticated_client_with_agent.get(f"/api/v1/chatbot/chat/{test_conversation.id}/messages")
        assert response.status_code == 200
        data = response.json()
        assert "messages" in data
        assert len(data["messages"]) == 2  # the turn above: "Hello", then the scripted "Hi there!"

    async def test_history_messages_have_role_and_content(self, authenticated_client_with_agent, test_conversation):
        await authenticated_client_with_agent.post(
            f"/api/v1/chatbot/chat/{test_conversation.id}", json={"message": "Hello"}
        )
        response = await authenticated_client_with_agent.get(f"/api/v1/chatbot/chat/{test_conversation.id}/messages")
        messages = response.json()["messages"]
        for msg in messages:
            assert "role" in msg
            assert "content" in msg

    async def test_long_reply_in_history_returns_200(
        self, authenticated_client_with_agent, test_conversation, scripted_model
    ):
        scripted_model.responses[:] = [AIMessage(content="x" * 5000)]
        await authenticated_client_with_agent.post(
            f"/api/v1/chatbot/chat/{test_conversation.id}", json={"message": "Explain budgeting"}
        )
        response = await authenticated_client_with_agent.get(f"/api/v1/chatbot/chat/{test_conversation.id}/messages")
        assert response.status_code == 200
        assert len(response.json()["messages"][1]["content"]) == 5000

    async def test_history_response_carries_activity(
        self, authenticated_client_with_agent, test_conversation, scripted_model, use_tools, monkeypatch
    ):
        # One step of reasoning and two lookups (one fails), then the cap ends the turn with a wrap-up.
        monkeypatch.setattr(settings.llm, "CHAT_MAX_STEPS", 2)
        use_tools(
            stub_tool("spending", "Spending by category", DISPLAY.model_dump()),
            stub_tool("income", "Income"),
        )
        reasoning = {
            "type": "reasoning",
            "index": 0,
            "summary": [{"index": 0, "type": "summary_text", "text": "Checking categories."}],
        }
        scripted_model.responses[:] = [
            AIMessage(content=[reasoning], tool_calls=[tool_call("spending", "c1"), tool_call("income", "c2")]),
            AIMessage(content="", tool_calls=[tool_call("spending", "c3")]),
            AIMessage(content="Mostly groceries."),
        ]
        await authenticated_client_with_agent.post(
            f"/api/v1/chatbot/chat/{test_conversation.id}", json={"message": "Where did my money go?"}
        )
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
        self, authenticated_client_with_agent, test_conversation, scripted_model, use_tools
    ):
        use_tools(stub_tool("spending", "Looking up spending", DISPLAY.model_dump()))
        scripted_model.responses[:] = [
            AIMessage(content="", tool_calls=[tool_call("spending", "c1")]),
            AIMessage(content="You spent €40."),
        ]

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

    async def test_a_turn_the_server_stopped_ends_in_done_stopped_and_reopens_stopped(
        self, authenticated_client_with_agent, test_conversation, scripted_model, use_tools, monkeypatch
    ):
        # The cap is one model call: the tool-calling response uses it, so the wrap-up text ends the turn.
        monkeypatch.setattr(settings.llm, "CHAT_MAX_STEPS", 1)
        use_tools(stub_tool("spending", "Looking up spending", DISPLAY.model_dump()))
        scripted_model.responses[:] = [
            AIMessage(content="", tool_calls=[tool_call("spending", "c1")]),
            AIMessage(content="Mostly groceries."),
        ]

        response = await authenticated_client_with_agent.post(
            f"/api/v1/chatbot/chat/{test_conversation.id}/stream",
            json={"message": "Hello"},
        )
        events = _events(response)
        assert events[-1] == {"type": "done", "stopped": True}

        history = await authenticated_client_with_agent.get(f"/api/v1/chatbot/chat/{test_conversation.id}/messages")
        [_, reply] = history.json()["messages"]
        assert reply["content"] == "Mostly groceries."
        assert reply["activity"]["stopped"] is True

    async def test_stream_failure_is_an_error_event_without_server_text(
        self, authenticated_client_with_agent, test_conversation, scripted_model
    ):
        # Text beside a call to a tool that does not exist (no tool events), then the next model call fails.
        scripted_model.responses[:] = [
            AIMessage(content="partial", tool_calls=[tool_call("no_such_tool", "c1")]),
            RuntimeError("model down"),
        ]

        response = await authenticated_client_with_agent.post(
            f"/api/v1/chatbot/chat/{test_conversation.id}/stream",
            json={"message": "Hello"},
        )
        events = _events(response)
        assert events == [{"type": "text", "text": "partial"}, {"type": "error"}]


class TestStreamClientDisconnect:
    """WS7: a client that leaves mid-stream stops the model call."""

    async def test_disconnect_cancels_the_agent_stream(
        self, authenticated_client_with_agent, test_conversation, scripted_model
    ):
        first_chunk_sent = asyncio.Event()
        cancelled = asyncio.Event()

        async def slow_model():
            # Called after the first reply's text has streamed.
            first_chunk_sent.set()
            try:
                await asyncio.sleep(30)  # a model still generating
            except asyncio.CancelledError:
                cancelled.set()
                raise
            return AIMessage(content="never")

        scripted_model.responses[:] = [
            AIMessage(content="first", tool_calls=[tool_call("no_such_tool", "c1")]),
            slow_model,
        ]

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


class TestFinanceToolsThroughTheRoute:
    """The startup injection end to end: the agent `main.py` builds, a model that asks for a
    finance lookup, the stream route, and the signed-in user's transactions."""

    async def test_a_lookup_reads_the_users_data_and_its_result_reaches_the_model(
        self,
        authenticated_client,
        db_session,
        test_user,
        other_user,
        add,
        test_conversation,
        monkeypatch,
        scripted_model,
    ):
        monkeypatch.setattr(analytics_service_module, "_today", lambda: dt.date(2026, 10, 16))
        await add(test_user, "2026-09-05", "-180.50", merchant="Lidl")
        await add(test_user, "2026-09-25", "2100.00", category="salary", merchant="Employer")
        await add(other_user, "2026-09-07", "-9999.00", merchant="Secret Boutique")

        tools = chat_tools()
        agent = ChatbotAgent(build_chatbot(MemorySaver(), tools, chat_preamble, model=scripted_model), tools)
        call = {"name": "spending_overview", "args": {"months": 1}, "id": "c1", "type": "tool_call"}
        scripted_model.responses[:] = [
            AIMessage(content="", tool_calls=[call]),
            AIMessage(content="You spent €180.50 in September 2026."),
        ]

        @asynccontextmanager
        async def sessions():
            yield db_session  # the test's session, so the tool sees the seeded rows

        app.dependency_overrides[get_chatbot_agent] = lambda: agent
        try:
            with (
                patch("app.agents.chatbot.middleware.memory.get_relevant_memory", new=AsyncMock(return_value="")),
                patch("app.agents.chatbot.middleware.memory.update_memory", new=AsyncMock()),
                patch.object(app.state, "session_factory", sessions, create=True),
            ):
                response = await authenticated_client.post(
                    f"/api/v1/chatbot/chat/{test_conversation.id}/stream",
                    json={"message": "How much did I spend last month?"},
                )
        finally:
            app.dependency_overrides.pop(get_chatbot_agent, None)
        route = (await authenticated_client.get("/api/v1/analytics/spending", params={"months": 1})).json()

        events = _events(response)
        assert [e["type"] for e in events] == ["tool_started", "tool_finished", "text", "done"]
        assert events[0] == {
            "type": "tool_started",
            "id": "c1",
            "name": "spending_overview",
            "title": "Spending overview",
        }
        finished = events[1]
        assert finished["ok"] is True and finished["display"]["period"] == "September 2026"
        spent = next(item for item in finished["display"]["summary"] if item["label"] == "spent")
        # The amount the analytics route returns, as the same decimal string: never a float.
        assert spent["value"] == route["total_expenses"] == "180.50" and spent["kind"] == "total"
        # The second model call is sent the tool's result: this user's figures, nobody else's.
        [result] = [m for m in scripted_model.sent[1] if isinstance(m, ToolMessage)]
        assert result.tool_call_id == "c1" and "expenses 180.50 EUR" in result.content
        assert "9999" not in result.content
        assert events[-1] == {"type": "done", "stopped": False}
