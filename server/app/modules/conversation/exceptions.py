"""Conversation service domain exceptions."""

from app.exceptions.base import NotFoundError


class ConversationNotFoundError(NotFoundError):
    """Exception raised when a conversation is not found."""

    error_code = "CONVERSATION_NOT_FOUND"
