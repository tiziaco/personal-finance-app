"""Ids leave for LangGraph, Langfuse and mem0 as text."""

from unittest.mock import patch

import pytest
from uuid_utils.compat import uuid7

from app.agents.shared.observability.langfuse import create_graph_config, create_trace_config

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


def test_a_trace_config_groups_calls_by_session_and_names_the_run():
    user_id, session_id = uuid7(), uuid7()
    config = create_trace_config(user_id, session_id, "transaction_labeler")
    assert config["run_name"] == "transaction_labeler"
    assert config["metadata"]["langfuse_user_id"] == str(user_id)
    assert config["metadata"]["langfuse_session_id"] == str(session_id)
    assert "transaction_labeler" in config["metadata"]["langfuse_tags"]
    assert "configurable" not in config


def test_a_trace_config_takes_extra_metadata():
    config = create_trace_config(uuid7(), uuid7(), "transaction_labeler", metadata={"prompt_version": "v2"})
    assert config["metadata"]["prompt_version"] == "v2"
    assert config["metadata"]["environment"]
