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

    def test_script_tag_rejected(self):
        with pytest.raises(ValidationError, match="script"):
            Message(role="user", content="<script>alert('xss')</script>")

    def test_null_bytes_rejected(self):
        with pytest.raises(ValidationError, match="null bytes"):
            Message(role="user", content="hello\0world")

    def test_max_length_boundary(self):
        msg = Message(role="user", content="a" * 3000)
        assert len(msg.content) == 3000

    def test_over_max_length_rejected(self):
        with pytest.raises(ValidationError):
            Message(role="user", content="a" * 3001)

    def test_extra_fields_ignored(self):
        msg = Message(role="user", content="hello", extra_field="ignored")
        assert not hasattr(msg, "extra_field")
