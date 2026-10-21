"""A model call whose answer must be JSON of a known shape."""

from unittest.mock import patch

import httpx
import pytest
from langchain_core.messages import HumanMessage, SystemMessage
from openai import RateLimitError
from pydantic import RootModel

from app.agents.core.structured import InvalidModelAnswer, ask, parse_answer
from app.integrations.llm import LLMRateLimitError
from tests.unit.agents.fakes import FakeModel

pytestmark = pytest.mark.unit


class Mapping(RootModel[dict[str, str]]):
    pass


def rate_limited() -> RateLimitError:
    request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    return RateLimitError("slow down", response=httpx.Response(429, request=request), body=None)


def test_parses_plain_and_fenced_json():
    assert parse_answer('{"a": "date"}', Mapping).root == {"a": "date"}
    assert parse_answer('```json\n{"a": "date"}\n```', Mapping).root == {"a": "date"}


def test_rejects_prose_and_the_wrong_shape():
    with pytest.raises(InvalidModelAnswer):
        parse_answer("Sure! Here it is", Mapping)
    with pytest.raises(InvalidModelAnswer):
        parse_answer('["a"]', Mapping)


async def test_returns_the_shape_on_a_valid_answer():
    model = FakeModel('{"a": "date"}')
    answer = await ask(Mapping, "system", "user", {}, model=model)
    assert answer.root == {"a": "date"}
    assert len(model.calls) == 1
    [system, human] = model.calls[0][0]
    assert system == SystemMessage(content="system")
    assert human == HumanMessage(content="user")


async def test_asks_once_more_after_an_invalid_answer():
    model = FakeModel("not json", '{"a": "b"}')
    answer = await ask(Mapping, "system", "user", {}, model=model)
    assert answer.root == {"a": "b"}
    assert len(model.calls) == 2


async def test_gives_up_after_two_invalid_answers():
    model = FakeModel("nope")
    with pytest.raises(InvalidModelAnswer):
        await ask(Mapping, "system", "user", {}, model=model)
    assert len(model.calls) == 2


async def test_a_model_error_propagates_translated_without_a_second_ask():
    model = FakeModel(rate_limited())
    with pytest.raises(LLMRateLimitError):
        await ask(Mapping, "system", "user", {}, model=model)
    assert len(model.calls) == 1


async def test_the_config_reaches_the_model():
    model = FakeModel("nope", '{"a": "b"}')
    await ask(Mapping, "system", "user", {"callbacks": ["trace"]}, model=model)
    assert [config for _, config in model.calls] == [{"callbacks": ["trace"]}] * 2


async def test_without_a_model_it_asks_the_primary_with_its_fallbacks():
    model = FakeModel('{"a": "b"}')
    with (
        patch("app.agents.core.structured.chat_model", return_value="primary") as primary,
        patch("app.agents.core.structured.with_fallbacks", return_value=model) as wrap,
    ):
        answer = await ask(Mapping, "system", "user", {})
    wrap.assert_called_once_with(primary.return_value)
    assert answer.root == {"a": "b"}
