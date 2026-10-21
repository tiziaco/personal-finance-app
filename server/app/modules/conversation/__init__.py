"""Conversation — a user's chat threads and the chatbot that answers in them.

This is the public surface. Another module imports from here and nowhere
deeper (docs/architecture/server.md, R1).
"""

from app.modules.conversation.dependencies import (  # noqa: I001
    ChatbotAgentDep,
    UserConversation,
    get_chatbot_agent,
    get_user_conversation,
)
from app.modules.conversation.exceptions import (
    ConversationNotFoundError,
)
from app.modules.conversation.router import router
from app.modules.conversation.schemas import ConversationResponse
from app.modules.conversation.service import conversation_service
from app.modules.conversation.tools import chat_preamble, chat_tools

# @events.on is a module-level side effect: importing the root is what subscribes.
from app.modules.conversation import handlers

__all__ = [
    "ChatbotAgentDep",
    "ConversationNotFoundError",
    "ConversationResponse",
    "UserConversation",
    "chat_preamble",
    "chat_tools",
    "conversation_service",
    "get_chatbot_agent",
    "get_user_conversation",
    "router",
]
