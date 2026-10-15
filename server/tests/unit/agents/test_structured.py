"""A model call whose answer must be JSON of a known shape."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage
from pydantic import RootModel
from tenacity import wait_none

from app.agents.shared import structured
from app.agents.shared.structured import InvalidModelAnswer, ask_json, parse_answer
from app.integrations.llm import LLMAPIError

pytestmark = pytest.mark.unit


class Mapping(RootModel[dict[str, str]]):
    pass


@pytest.fixture(autouse=True)
def no_backoff():
    """The retry's real backoff would sleep a second; tenacity reads `wait` from the decorated function."""
    original = structured._ask_once.retry.wait
    structured._ask_once.retry.wait = wait_none()
    yield
    structured._ask_once.retry.wait = original


def test_parses_plain_and_fenced_json():
    assert parse_answer('{"a": "date"}', Mapping).root == {"a": "date"}
    assert parse_answer('```json\n{"a": "date"}\n```', Mapping).root == {"a": "date"}


def test_rejects_prose_and_the_wrong_shape():
    with pytest.raises(InvalidModelAnswer):
        parse_answer("Sure! Here it is", Mapping)
    with pytest.raises(InvalidModelAnswer):
        parse_answer('["a"]', Mapping)


async def test_asks_once_more_after_an_invalid_answer():
    service = MagicMock()
    service.call = AsyncMock(side_effect=[AIMessage(content="nope"), AIMessage(content='{"a": "date"}')])
    answer = await ask_json(service, "system", "user", Mapping, {"callbacks": []})
    assert answer.root == {"a": "date"}
    assert service.call.await_count == 2
    assert service.call.await_args.kwargs["config"] == {"callbacks": []}


async def test_gives_up_after_two_invalid_answers():
    service = MagicMock()
    service.call = AsyncMock(return_value=AIMessage(content="nope"))
    with pytest.raises(InvalidModelAnswer):
        await ask_json(service, "system", "user", Mapping, {})
    assert service.call.await_count == 2


async def test_a_model_error_propagates_without_a_second_ask():
    service = MagicMock()
    service.call = AsyncMock(side_effect=LLMAPIError("down"))
    with pytest.raises(LLMAPIError):
        await ask_json(service, "system", "user", Mapping, {})
    assert service.call.await_count == 1
