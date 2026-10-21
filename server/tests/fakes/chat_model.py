"""A scripted chat model: the seam that drives the real chat graph and its middleware in tests."""

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class ScriptedChatModel(BaseChatModel):
    """Answers each model call with the next entry of `responses` and records the request in `sent`.

    An entry is an `AIMessage`, an exception to raise, or a zero-argument async callable
    returning an `AIMessage` (so a test can hold a call open until it is cancelled, or
    look at the world while the call is in flight). Each answer is a copy, so one message
    scripted twice gets two ids. `bind_tools` records the tools and returns the model
    itself: every call of a turn shares the one queue.
    """

    responses: list[Any]
    sent: list[list[BaseMessage]] = []
    bound_tools: list = []

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "ScriptedChatModel":
        self.bound_tools = list(tools)
        return self

    def _generate(self, messages: list[BaseMessage], stop: Any = None, run_manager: Any = None, **kwargs: Any):
        raise NotImplementedError("async only")

    async def _agenerate(
        self, messages: list[BaseMessage], stop: Any = None, run_manager: Any = None, **kwargs: Any
    ) -> ChatResult:
        self.sent.append(list(messages))
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        if callable(response):
            response = await response()
        return ChatResult(generations=[ChatGeneration(message=response.model_copy())])
