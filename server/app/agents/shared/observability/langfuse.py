"""Langfuse observability utilities for agents."""

import uuid
from typing import Optional

from langchain_core.runnables import RunnableConfig
from langfuse.langchain import CallbackHandler

from app.core.config import settings


def _metadata(user: Optional[str], session: str, tags: list[str]) -> dict:
    """What every trace carries: its user, the session it groups under, the environment."""
    return {
        # Standard metadata
        "user_id": user,
        "environment": settings.ENVIRONMENT.value,
        # Langfuse-specific metadata keys (v3 approach)
        "langfuse_user_id": user,
        "langfuse_session_id": session,
        "langfuse_tags": [settings.ENVIRONMENT.value, *tags],
    }


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
        "metadata": {**_metadata(user, thread_id, []), "conversation_id": thread_id},
    }


def create_trace_config(
    user_id: uuid.UUID, session_id: uuid.UUID, name: str, metadata: Optional[dict] = None
) -> RunnableConfig:
    """Langfuse config for a model call made outside a graph.

    Traced to the user, grouped by `session_id` (an import's upload id), named
    `name`, with `metadata` added. No thread id: nothing is checkpointed.
    """
    return {
        "callbacks": [CallbackHandler()],
        "run_name": name,
        "metadata": {**_metadata(str(user_id), str(session_id), [name]), **(metadata or {})},
    }
