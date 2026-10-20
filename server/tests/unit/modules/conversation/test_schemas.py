"""Tests for app.modules.conversation.schemas — validation, sanitization, serialization."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from uuid_utils.compat import uuid7

from app.agents.messages import ChatMessage
from app.modules.conversation.schemas import (
    ChatRequest,
    ChatResponse,
    ConversationHistory,
    ConversationResponse,
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
        msg = ChatMessage(role="assistant", content="Hello!")
        resp = ChatResponse(message=msg)
        assert resp.message.content == "Hello!"


class TestConversationHistory:
    """Tests for ConversationHistory schema."""

    def test_valid_history(self):
        messages = [
            ChatMessage(role="user", content="Hi"),
            ChatMessage(role="assistant", content="Hello!"),
        ]
        history = ConversationHistory(messages=messages)
        assert len(history.messages) == 2


class TestConversationResponse:
    """Tests for ConversationResponse."""

    def test_valid_response(self):
        resp = ConversationResponse(
            conversation_id=uuid7(),
            name="My Chat",
            created_at=datetime.now(UTC),
        )
        assert resp.name == "My Chat"

    @pytest.mark.parametrize("name", ["<script>alert</script>", 'test{name}[0]("val")', "O'Brien's `trip`"])
    def test_name_is_returned_verbatim(self, name):
        """Escaping is the renderer's job — the response carries the stored name unchanged."""
        resp = ConversationResponse(
            conversation_id=uuid7(),
            name=name,
            created_at=datetime.now(UTC),
        )
        assert resp.name == name

    def test_empty_name_allowed(self):
        resp = ConversationResponse(
            conversation_id=uuid7(),
            name="",
            created_at=datetime.now(UTC),
        )
        assert resp.name == ""


class TestChatRequestInputRules:
    """The rules on what a user may send live on the request, not on the message models."""

    def test_script_tag_rejected(self):
        with pytest.raises(ValidationError, match="script"):
            ChatRequest(message="<script>alert('xss')</script>")

    def test_null_bytes_rejected(self):
        with pytest.raises(ValidationError, match="null bytes"):
            ChatRequest(message="hello\0world")

    def test_max_length_boundary(self):
        assert len(ChatRequest(message="a" * 3000).message) == 3000

    def test_over_max_length_rejected(self):
        with pytest.raises(ValidationError):
            ChatRequest(message="a" * 3001)
