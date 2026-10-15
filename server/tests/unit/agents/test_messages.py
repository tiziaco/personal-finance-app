"""Tests for the Message schema."""

import pytest
from pydantic import ValidationError

from app.agents.messages import Message

pytestmark = pytest.mark.unit


class TestMessage:
    """Tests for Message schema."""

    def test_valid_user_message(self):
        msg = Message(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_valid_assistant_message(self):
        msg = Message(role="assistant", content="Hi there")
        assert msg.role == "assistant"

    def test_valid_system_message(self):
        msg = Message(role="system", content="You are helpful")
        assert msg.role == "system"

    def test_invalid_role_rejected(self):
        with pytest.raises(ValidationError):
            Message(role="admin", content="hello")

    def test_empty_content_rejected(self):
        with pytest.raises(ValidationError):
            Message(role="user", content="")

    def test_long_assistant_reply_accepted(self):
        """History carries whole replies, and a reply has no 3,000-character cap."""
        msg = Message(role="assistant", content="a" * 10_000)
        assert len(msg.content) == 10_000

    def test_reply_quoting_a_script_tag_accepted(self):
        """A reply may quote markup in a code block; input rules apply to ChatRequest, not here."""
        msg = Message(role="assistant", content="```html\n<script>alert(1)</script>\n```")
        assert "<script>" in msg.content

    def test_extra_fields_ignored(self):
        msg = Message(role="user", content="hello", extra_field="ignored")
        assert not hasattr(msg, "extra_field")
