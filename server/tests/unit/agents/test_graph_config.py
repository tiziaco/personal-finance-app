"""Ids leave for LangGraph, Langfuse and mem0 as text."""

from unittest.mock import patch

import pytest
from uuid_utils.compat import uuid7

from app.agents.shared.observability.langfuse import create_graph_config

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def no_langfuse_client():
    with patch("app.agents.shared.observability.langfuse.CallbackHandler"):
        yield


def test_ids_are_text_in_the_thread_id_and_the_metadata():
    conversation_id, user_id = uuid7(), uuid7()

    config = create_graph_config(conversation_id, user_id)

    assert config["configurable"]["thread_id"] == str(conversation_id)
    metadata = config["metadata"]
    assert metadata["conversation_id"] == metadata["langfuse_session_id"] == str(conversation_id)
    assert metadata["user_id"] == metadata["langfuse_user_id"] == str(user_id)


def test_no_user_stays_none():
    assert create_graph_config(uuid7())["metadata"]["user_id"] is None
