"""Langfuse observability utilities for agents."""

import uuid
from typing import Optional

from langfuse.langchain import CallbackHandler

from app.core.config import settings


def create_graph_config(
    conversation_id: uuid.UUID,
    user_id: Optional[uuid.UUID] = None,
) -> dict:
    """Create a standard graph configuration dictionary.

    Ids go in as text: LangGraph's checkpoint tables, Langfuse and mem0 metadata store strings.

    Args:
        conversation_id: The conversation/thread ID.
        user_id: Optional user ID for tracking.

    Returns:
        Configuration dictionary with callbacks and metadata.
    """
    thread_id = str(conversation_id)
    user = str(user_id) if user_id is not None else None
    return {
        "configurable": {"thread_id": thread_id},
        "callbacks": [CallbackHandler()],
        "metadata": {
            # Standard metadata
            "user_id": user,
            "conversation_id": thread_id,
            "environment": settings.ENVIRONMENT.value,
            "debug": settings.DEBUG,
            # Langfuse-specific metadata keys (v3 approach)
            "langfuse_user_id": user,
            "langfuse_session_id": thread_id,
            "langfuse_tags": [settings.ENVIRONMENT.value],
        },
    }
