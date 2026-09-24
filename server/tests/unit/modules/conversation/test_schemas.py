"""Tests for app.modules.conversation.schemas — validation, sanitization, serialization."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.agents.messages import Message
from app.modules.conversation.schemas import (
    ChatRequest,
    ChatResponse,
    ConversationHistory,
    ConversationResponse,
    StreamResponse,
)

pytestmark = pytest.mark.unit


class TestChatRequest:
    """Tests for ChatRequest schema."""

    def test_valid_request(self):
        req = ChatRequest(message="Hello, how are you?")
        assert req.message == "Hello, how are you?"

    def test_empty_message_rejected(self):
        with pytest.raises(ValidationError):
            ChatRequest(message="")

    def test_over_max_length_rejected(self):
        with pytest.raises(ValidationError):
            ChatRequest(message="a" * 3001)


class TestChatResponse:
    """Tests for ChatResponse schema."""

    def test_valid_response(self):
        msg = Message(role="assistant", content="Hello!")
        resp = ChatResponse(message=msg)
        assert resp.message.content == "Hello!"


class TestConversationHistory:
    """Tests for ConversationHistory schema."""

    def test_valid_history(self):
        messages = [
            Message(role="user", content="Hi"),
            Message(role="assistant", content="Hello!"),
        ]
        history = ConversationHistory(messages=messages)
        assert len(history.messages) == 2


class TestStreamResponse:
    """Tests for StreamResponse schema."""

    def test_defaults(self):
        resp = StreamResponse()
        assert resp.content == ""
        assert resp.done is False

    def test_with_content(self):
        resp = StreamResponse(content="chunk", done=True)
        assert resp.content == "chunk"
        assert resp.done is True


class TestConversationResponse:
    """Tests for ConversationResponse."""

    def test_valid_response(self):
        resp = ConversationResponse(
            conversation_id="abc-123",
            name="My Chat",
            created_at=datetime.now(UTC),
        )
        assert resp.name == "My Chat"

    @pytest.mark.parametrize("name", ["<script>alert</script>", 'test{name}[0]("val")', "O'Brien's `trip`"])
    def test_name_is_returned_verbatim(self, name):
        """Escaping is the renderer's job — the response carries the stored name unchanged."""
        resp = ConversationResponse(
            conversation_id="abc-123",
            name=name,
            created_at=datetime.now(UTC),
        )
        assert resp.name == name

    def test_empty_name_allowed(self):
        resp = ConversationResponse(
            conversation_id="abc-123",
            name="",
            created_at=datetime.now(UTC),
        )
        assert resp.name == ""
